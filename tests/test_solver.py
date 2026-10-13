import torch

from robust_flower.noise import add_gaussian_noise
from robust_flower.operators import IdentityOperator
from robust_flower.solver import FlowerInverseSolver, conjugate_gradient


class ZeroVelocity(torch.nn.Module):
    def forward(self, x: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        return torch.zeros_like(x)


def test_corruption_is_reproducible() -> None:
    clean = torch.zeros(1, 1, 8, 8)
    variance = torch.full_like(clean, 0.04)
    first, first_noise = add_gaussian_noise(clean, variance, seed=7)
    second, second_noise = add_gaussian_noise(clean, variance, seed=7)
    assert torch.equal(first, second)
    assert torch.equal(first_noise, second_noise)


def test_identity_refinement_matches_conjugate_gradient() -> None:
    measurement = torch.randn(1, 1, 4, 4)
    destination = torch.randn_like(measurement)
    variance = torch.tensor([[[[0.13]]]])
    lam = 0.7
    operator = IdentityOperator()
    closed = operator.refine(measurement, destination, variance, lam)
    linear = lambda x: x / variance + x / lam
    rhs = measurement / variance + destination / lam
    cg, _ = conjugate_gradient(linear, rhs, max_iterations=100)
    assert torch.allclose(closed, cg, atol=1e-5, rtol=1e-5)


def test_solver_is_deterministic_for_fixed_seed() -> None:
    solver = FlowerInverseSolver(ZeroVelocity(), IdentityOperator(), steps=4)
    measurement = torch.zeros(1, 1, 8, 8)
    first = solver.reconstruct(measurement, 0.2, seed=11).image
    second = solver.reconstruct(measurement, 0.2, seed=11).image
    assert torch.equal(first, second)


def test_smaller_sigma_weights_measurement_more_strongly() -> None:
    measurement = torch.ones(1, 1, 4, 4)
    destination = torch.zeros_like(measurement)
    operator = IdentityOperator()
    low = operator.refine(measurement, destination, torch.tensor([[[[0.01]]]]), 0.5)
    high = operator.refine(measurement, destination, torch.tensor([[[[0.25]]]]), 0.5)
    assert float(low.mean()) > float(high.mean())


def test_shared_batch_noise_matches_separate_paired_runs() -> None:
    solver = FlowerInverseSolver(ZeroVelocity(), IdentityOperator(), steps=4)
    measurement = torch.zeros(1, 1, 8, 8)
    sigmas = torch.tensor([0.1, 0.2, 0.3])
    batched = solver.reconstruct(
        measurement.expand(3, -1, -1, -1),
        sigmas,
        seed=17,
        shared_noise_across_batch=True,
    ).image
    separate = torch.cat(
        [solver.reconstruct(measurement, float(sigma), seed=17).image for sigma in sigmas],
        dim=0,
    )
    assert torch.allclose(batched, separate)


def test_trajectory_capture_uses_requested_times() -> None:
    solver = FlowerInverseSolver(ZeroVelocity(), IdentityOperator(), steps=4)
    result = solver.reconstruct(
        torch.zeros(1, 1, 4, 4),
        0.2,
        seed=4,
        capture_times=(0.5, 1.0),
        capture_internal_times=(0.25, 0.75),
    )
    assert set(result.trajectory or {}) == {0.5, 1.0}
    assert set(result.internals or {}) == {0.25, 0.75}
