"""FLOWER solvers with explicit true/assumed noise separation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import torch

from .noise import cpu_generator, randn_like_cpu_seeded
from .operators import LinearOperator


@dataclass
class ReconstructionResult:
    image: torch.Tensor
    trajectory: dict[float, torch.Tensor] | None = None
    internals: dict[float, dict[str, torch.Tensor]] | None = None


class FlowerInverseSolver:
    """FLOWER-1 for a linear inverse problem and scalar Gaussian noise.

    ``assumed_sigma`` controls only the likelihood term. The measurement,
    degradation operator, model, and random source trajectory are independent
    of it, which makes paired mismatch comparisons possible.
    """

    def __init__(
        self,
        velocity_model: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
        operator: LinearOperator,
        *,
        steps: int,
        gamma: int = 0,
        cg_max_iterations: int = 50,
        cg_tolerance: float = 1e-5,
    ) -> None:
        if steps <= 0:
            raise ValueError("steps must be positive")
        if gamma != 0:
            raise ValueError("This benchmark isolates deterministic FLOWER-1 (gamma=0)")
        self.velocity_model = velocity_model
        self.operator = operator
        self.steps = int(steps)
        self.gamma = int(gamma)
        self.cg_max_iterations = int(cg_max_iterations)
        self.cg_tolerance = float(cg_tolerance)

    @staticmethod
    def _sigma_batch(
        assumed_sigma: float | torch.Tensor,
        *,
        batch_size: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> torch.Tensor:
        sigma = torch.as_tensor(assumed_sigma, device=device, dtype=dtype)
        if sigma.ndim == 0:
            sigma = sigma.repeat(batch_size)
        if sigma.ndim == 1 and sigma.shape[0] == batch_size:
            sigma = sigma[:, None, None, None]
        if sigma.shape != (batch_size, 1, 1, 1):
            raise ValueError("assumed_sigma must be scalar, B, or B x 1 x 1 x 1")
        if torch.any(sigma <= 0):
            raise ValueError("assumed_sigma must be strictly positive")
        return sigma

    def _refine(
        self,
        measurement: torch.Tensor,
        destination: torch.Tensor,
        sigma: torch.Tensor,
        lam: float,
    ) -> torch.Tensor:
        variance = sigma.square()
        refine = getattr(self.operator, "refine", None)
        if refine is not None:
            return refine(measurement, destination, variance, lam)

        adjoint_measurement = self.operator.adjoint(measurement)
        right_hand_side = adjoint_measurement / variance + destination / lam

        def normal_operator(image: torch.Tensor) -> torch.Tensor:
            return (
                self.operator.adjoint(self.operator.forward(image)) / variance
                + image / lam
            )

        refined, _ = conjugate_gradient(
            normal_operator,
            right_hand_side,
            initial=destination,
            max_iterations=self.cg_max_iterations,
            tolerance=self.cg_tolerance,
        )
        return refined

    def reconstruct(
        self,
        measurement: torch.Tensor,
        assumed_sigma: float | torch.Tensor,
        *,
        seed: int | None = None,
        generator: torch.Generator | None = None,
        shared_noise_across_batch: bool = False,
        noise_groups: list[tuple[torch.Generator, int]] | None = None,
        capture_times: tuple[float, ...] = (),
        capture_internal_times: tuple[float, ...] = (),
    ) -> ReconstructionResult:
        if measurement.ndim != 4:
            raise ValueError("measurement must have shape B x C x H x W")
        option_count = int(seed is not None) + int(generator is not None) + int(noise_groups is not None)
        if option_count != 1:
            raise ValueError("provide exactly one of seed, generator, or noise_groups")
        if noise_groups is not None and sum(size for _, size in noise_groups) != measurement.shape[0]:
            raise ValueError("noise_groups sizes must sum to the measurement batch size")

        domain_reference = self.operator.adjoint(measurement)
        sigma = self._sigma_batch(
            assumed_sigma,
            batch_size=measurement.shape[0],
            device=domain_reference.device,
            dtype=domain_reference.dtype,
        )
        if generator is None:
            generator = cpu_generator(int(seed)) if seed is not None else noise_groups[0][0]

        def sample_noise(reference: torch.Tensor) -> torch.Tensor:
            if noise_groups is not None:
                samples: list[torch.Tensor] = []
                offset = 0
                for group_generator, group_size in noise_groups:
                    sample = randn_like_cpu_seeded(reference[offset : offset + 1], group_generator)
                    samples.append(sample.expand(group_size, -1, -1, -1).clone())
                    offset += group_size
                return torch.cat(samples, dim=0)
            if shared_noise_across_batch and reference.shape[0] > 1:
                sample = randn_like_cpu_seeded(reference[:1], generator)
                return sample.expand_as(reference).clone()
            return randn_like_cpu_seeded(reference, generator)

        requested_trajectory = {
            max(1, min(self.steps, int(round(time * self.steps)))): float(time)
            for time in capture_times
        }
        requested_internals = {
            max(0, min(self.steps - 1, int(round(time * self.steps)))): float(time)
            for time in capture_internal_times
        }
        trajectory: dict[float, torch.Tensor] = {}
        internals: dict[float, dict[str, torch.Tensor]] = {}
        x = sample_noise(domain_reference)
        delta = 1.0 / self.steps
        batch_times = torch.ones(measurement.shape[0], device=measurement.device)

        with torch.inference_mode():
            for iteration in range(self.steps):
                t = delta * iteration
                sigma_r = (1.0 - t) / ((t * t + (1.0 - t) ** 2) ** 0.5)
                velocity = self.velocity_model(x, batch_times * t)
                destination = x + (1.0 - t) * velocity
                refined = self._refine(measurement, destination, sigma, sigma_r**2)
                source_noise = sample_noise(x)
                next_x = (t + delta) * refined + (1.0 - t - delta) * source_noise

                if iteration in requested_internals:
                    key = requested_internals[iteration]
                    internals[key] = {
                        "destination": destination.detach().cpu(),
                        "refined": refined.detach().cpu(),
                        "trajectory": next_x.detach().cpu(),
                    }
                if iteration + 1 in requested_trajectory:
                    trajectory[requested_trajectory[iteration + 1]] = next_x.detach().cpu()
                x = next_x

        return ReconstructionResult(
            image=x,
            trajectory=trajectory or None,
            internals=internals or None,
        )


def conjugate_gradient(
    operator: Callable[[torch.Tensor], torch.Tensor],
    right_hand_side: torch.Tensor,
    *,
    initial: torch.Tensor | None = None,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> tuple[torch.Tensor, int]:
    """Small batched conjugate-gradient helper for verification and extension."""

    x = torch.zeros_like(right_hand_side) if initial is None else initial.clone()
    residual = right_hand_side - operator(x)
    direction = residual.clone()
    dims = tuple(range(1, right_hand_side.ndim))
    residual_norm = residual.square().sum(dim=dims, keepdim=True)
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        applied = operator(direction)
        denominator = (direction * applied).sum(dim=dims, keepdim=True)
        alpha = residual_norm / denominator.clamp_min(torch.finfo(x.dtype).eps)
        x = x + alpha * direction
        residual = residual - alpha * applied
        next_norm = residual.square().sum(dim=dims, keepdim=True)
        if float(next_norm.sqrt().max()) < tolerance:
            break
        beta = next_norm / residual_norm.clamp_min(torch.finfo(x.dtype).eps)
        direction = residual + beta * direction
        residual_norm = next_norm
    return x, iterations
