import numpy as np
import torch

from robust_flower.operators import (
    GaussianBlurOperator,
    MaskOperator,
    SuperResolutionOperator,
    random_inpainting_mask,
)
from robust_flower.solver import FlowerInverseSolver


class ZeroVelocity(torch.nn.Module):
    def forward(self, x: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        return torch.zeros_like(x)


def test_superresolution_adjoint_identity() -> None:
    operator = SuperResolutionOperator(2)
    image = torch.randn(2, 3, 8, 8)
    measurement = torch.randn(2, 3, 4, 4)
    left = (operator.forward(image) * measurement).sum()
    right = (image * operator.adjoint(measurement)).sum()
    assert torch.allclose(left, right)


def test_gaussian_blur_adjoint_identity() -> None:
    operator = GaussianBlurOperator(
        image_size=16,
        sigma=1.0,
        kernel_size=5,
        channels=3,
        device=torch.device("cpu"),
    )
    image = torch.randn(2, 3, 16, 16)
    measurement = torch.randn_like(image)
    left = (operator.forward(image) * measurement).sum()
    right = (image * operator.adjoint(measurement)).sum()
    assert torch.allclose(left, right, atol=1e-4, rtol=1e-4)


def test_random_mask_matches_official_numpy_protocol() -> None:
    mask = random_inpainting_mask(
        8, missing_fraction=0.7, seed=42, device=torch.device("cpu")
    )
    expected = np.random.RandomState(42).binomial(1, 0.3, size=(1, 8, 8))
    assert torch.equal(mask[:, 0], torch.from_numpy(expected).float())


def test_inverse_solver_accepts_smaller_measurement_domain() -> None:
    operator = SuperResolutionOperator(2)
    solver = FlowerInverseSolver(ZeroVelocity(), operator, steps=2)
    measurement = torch.zeros(3, 1, 4, 4)
    result = solver.reconstruct(
        measurement,
        torch.tensor([0.05, 0.1, 0.2]),
        seed=3,
        shared_noise_across_batch=True,
    )
    assert result.image.shape == (3, 1, 8, 8)
    assert torch.isfinite(result.image).all()


def test_mask_operator_is_self_adjoint() -> None:
    mask = torch.tensor([[[[1.0, 0.0], [0.0, 1.0]]]])
    operator = MaskOperator(mask, name="test")
    image = torch.randn(2, 3, 2, 2)
    assert torch.equal(operator.forward(image), operator.adjoint(image))
