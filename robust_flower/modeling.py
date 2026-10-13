"""Loading helpers for the official FLOWER optimal-transport models."""

from __future__ import annotations

from pathlib import Path

import torch

from pnpflow.models import UNet


def resolve_device(requested: str = "auto") -> torch.device:
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def build_official_unet(image_size: int = 128) -> UNet:
    return UNet(
        input_channels=3,
        input_height=image_size,
        ch=32,
        ch_mult=(1, 2, 4, 8),
        num_res_blocks=6,
        attn_resolutions=(16, 8),
        resamp_with_conv=True,
    )


def load_official_model(
    checkpoint: str | Path,
    *,
    image_size: int,
    device: torch.device,
) -> UNet:
    checkpoint = Path(checkpoint)
    if not checkpoint.is_file():
        raise FileNotFoundError(
            f"Missing checkpoint: {checkpoint}. Download the official FLOWER weights first."
        )
    model = build_official_unet(image_size)
    try:
        state_dict = torch.load(checkpoint, map_location="cpu", weights_only=True)
    except TypeError:
        state_dict = torch.load(checkpoint, map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()
    return model.to(device)


def load_official_celeba_model(
    checkpoint: str | Path,
    *,
    device: torch.device,
) -> UNet:
    """Backward-compatible wrapper for the 128x128 CelebA checkpoint."""

    return load_official_model(checkpoint, image_size=128, device=device)
