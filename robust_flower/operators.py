"""Linear degradation operators matching the public FLOWER benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import torch


class LinearOperator(Protocol):
    name: str
    is_identity: bool

    def forward(self, image: torch.Tensor) -> torch.Tensor: ...

    def adjoint(self, measurement: torch.Tensor) -> torch.Tensor: ...

    def refine(
        self,
        measurement: torch.Tensor,
        destination: torch.Tensor,
        variance: torch.Tensor,
        lam: float,
    ) -> torch.Tensor: ...


@dataclass
class IdentityOperator:
    name: str = "denoising"
    is_identity: bool = True

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        return image

    def adjoint(self, measurement: torch.Tensor) -> torch.Tensor:
        return measurement

    def refine(
        self,
        measurement: torch.Tensor,
        destination: torch.Tensor,
        variance: torch.Tensor,
        lam: float,
    ) -> torch.Tensor:
        return (measurement / variance + destination / lam) / (
            variance.reciprocal() + 1.0 / lam
        )


class MaskOperator:
    is_identity = False

    def __init__(self, mask: torch.Tensor, *, name: str) -> None:
        if mask.ndim != 4 or mask.shape[0] != 1:
            raise ValueError("mask must have shape 1 x 1|C x H x W")
        self.mask = mask
        self.name = name

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        return image * self.mask

    def adjoint(self, measurement: torch.Tensor) -> torch.Tensor:
        return measurement * self.mask

    def refine(
        self,
        measurement: torch.Tensor,
        destination: torch.Tensor,
        variance: torch.Tensor,
        lam: float,
    ) -> torch.Tensor:
        numerator = self.adjoint(measurement) / variance + destination / lam
        precision = self.mask / variance + 1.0 / lam
        return numerator / precision


class GaussianBlurOperator:
    name = "gaussian_deblurring"
    is_identity = False

    def __init__(
        self,
        *,
        image_size: int,
        sigma: float,
        kernel_size: int,
        channels: int,
        device: torch.device,
    ) -> None:
        coordinates = torch.arange(kernel_size, dtype=torch.float32)
        coordinates = coordinates - (kernel_size - 1) / 2
        one_d = torch.exp(-(coordinates.square()) / (2 * sigma**2))
        one_d = one_d / one_d.sum()
        kernel = torch.outer(one_d, one_d).to(device)
        frequency_filter = torch.zeros(
            (1, channels, image_size, image_size), device=device
        )
        frequency_filter[..., :kernel_size, :kernel_size] = kernel
        self.frequency_filter = torch.roll(
            frequency_filter,
            shifts=(-(kernel_size - 1) // 2, -(kernel_size - 1) // 2),
            dims=(2, 3),
        )

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        return torch.fft.ifft2(
            torch.fft.fft2(image) * torch.fft.fft2(self.frequency_filter)
        ).real

    def adjoint(self, measurement: torch.Tensor) -> torch.Tensor:
        return torch.fft.ifft2(
            torch.fft.fft2(measurement)
            * torch.conj(torch.fft.fft2(self.frequency_filter))
        ).real

    def refine(
        self,
        measurement: torch.Tensor,
        destination: torch.Tensor,
        variance: torch.Tensor,
        lam: float,
    ) -> torch.Tensor:
        frequency_filter = torch.fft.fft2(self.frequency_filter)
        numerator = (
            torch.conj(frequency_filter) * torch.fft.fft2(measurement) / variance
            + torch.fft.fft2(destination) / lam
        )
        precision = frequency_filter.abs().square() / variance + 1.0 / lam
        return torch.fft.ifft2(numerator / precision).real


class SuperResolutionOperator:
    name = "super_resolution"
    is_identity = False

    def __init__(self, scale_factor: int) -> None:
        if scale_factor <= 1:
            raise ValueError("scale_factor must be greater than one")
        self.scale_factor = int(scale_factor)

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        return image[..., :: self.scale_factor, :: self.scale_factor]

    def adjoint(self, measurement: torch.Tensor) -> torch.Tensor:
        batch, channels, height, width = measurement.shape
        result = measurement.new_zeros(
            batch,
            channels,
            height * self.scale_factor,
            width * self.scale_factor,
        )
        result[..., :: self.scale_factor, :: self.scale_factor] = measurement
        return result

    def refine(
        self,
        measurement: torch.Tensor,
        destination: torch.Tensor,
        variance: torch.Tensor,
        lam: float,
    ) -> torch.Tensor:
        adjoint = self.adjoint(measurement)
        support = self.adjoint(torch.ones_like(measurement))
        return (adjoint / variance + destination / lam) / (
            support / variance + 1.0 / lam
        )


def random_inpainting_mask(
    image_size: int,
    *,
    missing_fraction: float,
    seed: int,
    device: torch.device,
) -> torch.Tensor:
    if not 0 <= missing_fraction < 1:
        raise ValueError("missing_fraction must be in [0, 1)")
    # Match pnpflow.utils.random_mask exactly without modifying global NumPy RNG.
    random_state = np.random.RandomState(seed)
    keep = random_state.binomial(
        n=1,
        p=1.0 - missing_fraction,
        size=(1, image_size, image_size),
    )
    return torch.from_numpy(keep).unsqueeze(1).to(device=device, dtype=torch.float32)


def box_inpainting_mask(
    image_size: int,
    *,
    box_size: int,
    device: torch.device,
) -> torch.Tensor:
    if box_size <= 0 or box_size > image_size:
        raise ValueError("box_size must lie in (0, image_size]")
    mask = torch.ones((1, 1, image_size, image_size), device=device)
    start = (image_size - box_size) // 2
    mask[..., start : start + box_size, start : start + box_size] = 0
    return mask


def build_operator(
    task_name: str,
    task_config: dict[str, object],
    *,
    dataset_name: str,
    image_size: int,
    mask_seed: int,
    device: torch.device,
) -> LinearOperator:
    if task_name == "denoising":
        return IdentityOperator()
    if task_name == "gaussian_deblurring":
        blur_sigma = float(task_config["blur_sigma"][dataset_name])  # type: ignore[index]
        return GaussianBlurOperator(
            image_size=image_size,
            sigma=blur_sigma,
            kernel_size=int(task_config["kernel_size"]),
            channels=3,
            device=device,
        )
    if task_name == "super_resolution":
        scale_factor = int(task_config["scale_factor"][dataset_name])  # type: ignore[index]
        return SuperResolutionOperator(scale_factor)
    if task_name == "random_inpainting":
        mask = random_inpainting_mask(
            image_size,
            missing_fraction=float(task_config["missing_fraction"]),
            seed=mask_seed,
            device=device,
        )
        return MaskOperator(mask, name=task_name)
    if task_name == "box_inpainting":
        box_size = int(task_config["box_size"][dataset_name])  # type: ignore[index]
        return MaskOperator(
            box_inpainting_mask(image_size, box_size=box_size, device=device),
            name=task_name,
        )
    raise ValueError(f"Unknown inverse problem: {task_name}")
