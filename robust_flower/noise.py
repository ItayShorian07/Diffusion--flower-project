"""Gaussian measurement noise used by the mismatch benchmark."""

from __future__ import annotations

import torch


def cpu_generator(seed: int) -> torch.Generator:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    return generator


def randn_like_cpu_seeded(
    reference: torch.Tensor, generator: torch.Generator
) -> torch.Tensor:
    """Generate device-independent random noise and move it to the target."""

    sample = torch.randn(
        reference.shape,
        generator=generator,
        device="cpu",
        dtype=reference.dtype,
    )
    return sample.to(reference.device)


def add_gaussian_noise(
    clean: torch.Tensor,
    variance: torch.Tensor,
    *,
    seed: int | None = None,
    generator: torch.Generator | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Corrupt an image tensor with a diagonal Gaussian covariance map."""

    if clean.ndim != 4:
        raise ValueError("clean must have shape B x C x H x W")
    if variance.shape[-3:] != clean.shape[-3:]:
        raise ValueError("variance and clean image shapes are incompatible")
    if torch.any(variance <= 0):
        raise ValueError("variance values must be positive")
    if (seed is None) == (generator is None):
        raise ValueError("provide exactly one of seed or generator")
    if generator is None:
        generator = cpu_generator(int(seed))
    noise = randn_like_cpu_seeded(clean, generator) * variance.sqrt()
    return clean + noise, noise
