"""PSNR, SSIM, and LPIPS evaluation matching the paper's value ranges."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from ignite.metrics import SSIM
from skimage.metrics import peak_signal_noise_ratio


def to_unit_range(image: torch.Tensor) -> torch.Tensor:
    """Map the model's [-1, 1] tensors to clipped [0, 1] images."""

    return (image.detach().float() * 0.5 + 0.5).clamp(0.0, 1.0)


@dataclass
class MetricEvaluator:
    device: torch.device
    enable_lpips: bool = True
    paper_compatible: bool = True

    def __post_init__(self) -> None:
        self._lpips_model: Any | None = None

    def _get_lpips_model(self) -> Any:
        if self._lpips_model is None:
            import lpips

            self._lpips_model = lpips.LPIPS(net="alex").to(self.device).eval()
        return self._lpips_model

    def evaluate_each(
        self, clean: torch.Tensor, reconstruction: torch.Tensor
    ) -> list[dict[str, float]]:
        clean_01 = to_unit_range(clean)
        reconstruction_01 = to_unit_range(reconstruction)
        clean_np = clean_01.cpu().permute(0, 2, 3, 1).numpy()
        reconstruction_np = reconstruction_01.cpu().permute(0, 2, 3, 1).numpy()

        psnr_values: list[float] = []
        ssim_values: list[float] = []
        for index, (reference, estimate) in enumerate(
            zip(clean_np, reconstruction_np)
        ):
            psnr_values.append(
                float(peak_signal_noise_ratio(reference, estimate, data_range=1.0))
            )
            ssim_metric = SSIM(data_range=1.0)
            ssim_metric.update(
                (
                    reconstruction_01[index : index + 1].cpu(),
                    clean_01[index : index + 1].cpu(),
                )
            )
            ssim_values.append(float(ssim_metric.compute()))

        lpips_values = [math.nan] * clean.shape[0]
        if self.enable_lpips:
            lpips_clean = clean_01.to(self.device)
            lpips_reconstruction = reconstruction_01.to(self.device)
            if self.paper_compatible:
                # Match the public FLOWER metric helper exactly: it maps the
                # postprocessed images to [-1, 1] and also passes normalize=True.
                lpips_clean = 2.0 * lpips_clean - 1.0
                lpips_reconstruction = 2.0 * lpips_reconstruction - 1.0
            with torch.inference_mode():
                values = (
                    self._get_lpips_model()(
                        lpips_clean,
                        lpips_reconstruction,
                        normalize=True,
                    )
                    .flatten()
                    .cpu()
                )
                lpips_values = [float(value) for value in values]

        return [
            {"psnr": psnr, "ssim": ssim, "lpips": lpips_value}
            for psnr, ssim, lpips_value in zip(psnr_values, ssim_values, lpips_values)
        ]

    def evaluate(
        self, clean: torch.Tensor, reconstruction: torch.Tensor
    ) -> dict[str, float]:
        values = self.evaluate_each(clean, reconstruction)
        return {
            metric: float(np.mean([row[metric] for row in values]))
            for metric in ("psnr", "ssim", "lpips")
        }
