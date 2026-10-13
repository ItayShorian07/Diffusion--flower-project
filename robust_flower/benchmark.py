"""Shared data and image helpers for the benchmark and figure capture."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from PIL import Image
from torchvision.transforms import v2

from .metrics import to_unit_range


def image_transform(
    dataset: str,
    *,
    image_size: int,
    center_crop: int | None,
) -> v2.Compose:
    transforms: list[Any] = []
    if dataset == "celeba" and center_crop is not None:
        transforms.append(v2.CenterCrop(center_crop))
    transforms.extend(
        [
            v2.Resize((image_size, image_size)),
            v2.ToImage(),
            v2.ToDtype(torch.float32, scale=True),
            v2.Normalize(mean=[0.5] * 3, std=[0.5] * 3),
        ]
    )
    return v2.Compose(transforms)


def load_image(path: Path, transform: v2.Compose, device: torch.device) -> torch.Tensor:
    with Image.open(path) as source:
        image = transform(source.convert("RGB"))
    return image.unsqueeze(0).to(device)


def save_tensor_image(image: torch.Tensor, path: Path) -> None:
    array = (
        to_unit_range(image)[0]
        .detach()
        .cpu()
        .permute(1, 2, 0)
        .mul(255)
        .round()
        .byte()
        .numpy()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array).save(path)


def read_manifest(path: Path, root: Path, expected: int) -> list[Path]:
    names = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if len(names) != expected:
        raise ValueError(f"{path} contains {len(names)} entries; expected {expected}")
    paths = [root / name for name in names]
    missing = [candidate for candidate in paths if not candidate.is_file()]
    if missing:
        preview = ", ".join(str(candidate) for candidate in missing[:3])
        raise FileNotFoundError(f"Missing {len(missing)} benchmark images, including {preview}")
    return paths
