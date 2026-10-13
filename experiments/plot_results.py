#!/usr/bin/env python3
"""Create the five predefined figures for the FLOWER mismatch study."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


TASKS = [
    "denoising",
    "gaussian_deblurring",
    "super_resolution",
    "random_inpainting",
    "box_inpainting",
]
TASK_LABELS = {
    "denoising": "Denoising",
    "gaussian_deblurring": "Gaussian deblurring",
    "super_resolution": "Super-resolution",
    "random_inpainting": "Random inpainting",
    "box_inpainting": "Box inpainting",
}
DATASET_LABELS = {"celeba": "CelebA", "afhq_cat": "AFHQ-Cat"}
COLORS = ["#155E75", "#D97706", "#7C3AED", "#059669", "#BE123C"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("artifacts/experiments/main"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/figures"))
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def figure1(summary: list[dict[str, str]], output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 5.1), sharey=True)
    ratios = sorted({float(row["assumed_to_true_sigma"]) for row in summary})
    for axis, dataset in zip(axes, ("celeba", "afhq_cat")):
        for task, color in zip(TASKS, COLORS):
            rows = sorted(
                (row for row in summary if row["dataset"] == dataset and row["task"] == task),
                key=lambda row: float(row["assumed_to_true_sigma"]),
            )
            axis.errorbar(
                ratios,
                [float(row["psnr_delta_vs_correct_mean"]) for row in rows],
                yerr=[float(row["psnr_delta_vs_correct_ci95"]) for row in rows],
                color=color,
                marker="o",
                linewidth=2.0,
                markersize=5,
                capsize=3,
                label=TASK_LABELS[task],
            )
        axis.axhline(0, color="#263746", linewidth=1)
        axis.axvline(1, color="#7A8793", linewidth=1, linestyle="--")
        axis.set_title(DATASET_LABELS[dataset], fontweight="bold")
        axis.set_xlabel(r"Assumed noise ratio  $\sigma_a / \sigma_t$")
        axis.set_xticks(ratios)
        axis.grid(alpha=0.18)
    axes[0].set_ylabel(r"Paired $\Delta$PSNR relative to correct $\sigma$ (dB)")
    axes[1].legend(frameon=False, fontsize=9, loc="best")
    fig.suptitle("FLOWER sensitivity to measurement-noise scale mismatch", fontsize=16, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output / "figure1_delta_psnr.png", dpi=240, bbox_inches="tight")
    plt.close(fig)


def task_sensitivity(summary: list[dict[str, str]], dataset: str, task: str) -> float:
    values = [
        abs(float(row["psnr_delta_vs_correct_mean"]))
        for row in summary
        if row["dataset"] == dataset
        and row["task"] == task
        and float(row["assumed_to_true_sigma"]) != 1.0
    ]
    return float(np.mean(values))


def qualitative_figure(
    input_dir: Path,
    summary: list[dict[str, str]],
    *,
    dataset: str,
    output_path: Path,
) -> None:
    ranked = sorted(TASKS, key=lambda task: task_sensitivity(summary, dataset, task))
    selected_tasks = [ranked[-1], ranked[0]]
    ratios = [0.5, 0.75, 1.0, 1.25, 1.5]
    columns = [("ground_truth.png", "Ground truth"), ("measurement.png", "Measurement")]
    columns.extend((f"sigma_ratio_{ratio:g}.png", f"{ratio:g}x sigma") for ratio in ratios)
    fig, axes = plt.subplots(2, len(columns), figsize=(15.2, 5.1))

    for row_index, task in enumerate(selected_tasks):
        candidates = sorted(
            (input_dir / "reconstructions" / dataset / task).glob("image_*")
        )
        if len(candidates) != 1:
            raise FileNotFoundError(f"Expected one qualitative image directory for {dataset}/{task}")
        image_dir = candidates[0]
        for column_index, (filename, label) in enumerate(columns):
            axis = axes[row_index, column_index]
            axis.imshow(Image.open(image_dir / filename))
            axis.axis("off")
            if row_index == 0:
                axis.set_title(label, fontsize=10)
            if column_index == 0:
                sensitivity = task_sensitivity(summary, dataset, task)
                axis.set_ylabel(
                    f"{TASK_LABELS[task]}\nmean |delta| {sensitivity:.2f} dB",
                    fontsize=10,
                )
    fig.suptitle(
        f"{DATASET_LABELS[dataset]} final reconstructions for the most and least sensitive tasks",
        fontsize=15,
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)


def figure4(input_dir: Path, output: Path) -> None:
    root = input_dir / "analysis_capture"
    ratios = [0.5, 0.75, 1.0, 1.25, 1.5]
    times = [0.2, 0.4, 0.6, 0.8, 1.0]
    fig, axes = plt.subplots(len(ratios), len(times), figsize=(11.2, 11.0))
    for row_index, ratio in enumerate(ratios):
        for column_index, time_value in enumerate(times):
            path = root / "trajectory" / f"ratio_{ratio:g}" / f"t_{time_value:g}.png"
            axes[row_index, column_index].imshow(Image.open(path))
            axes[row_index, column_index].axis("off")
            if row_index == 0:
                axes[row_index, column_index].set_title(f"t = {time_value:g}")
            if column_index == 0:
                axes[row_index, column_index].set_ylabel(f"sigma ratio {ratio:g}")
    fig.suptitle("Reconstruction trajectories for the most sensitive setting", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output / "figure4_trajectory.png", dpi=240, bbox_inches="tight")
    plt.close(fig)


def figure5(input_dir: Path, output: Path) -> None:
    root = input_dir / "analysis_capture" / "internals"
    ratios = [0.5, 1.0, 1.5]
    times = [0.25, 0.5, 0.75]
    states = [
        ("destination", "Prior destination x-hat-1"),
        ("refined", "Measurement-refined mu-t"),
        ("trajectory", "Next trajectory state"),
    ]
    fig, axes = plt.subplots(3, 9, figsize=(18.0, 6.8))
    for row_index, ratio in enumerate(ratios):
        for time_index, time_value in enumerate(times):
            for state_index, (filename, label) in enumerate(states):
                column_index = time_index * len(states) + state_index
                path = root / f"ratio_{ratio:g}" / f"t_{time_value:g}" / f"{filename}.png"
                axis = axes[row_index, column_index]
                axis.imshow(Image.open(path))
                axis.axis("off")
                if row_index == 0:
                    axis.set_title(f"t={time_value:g}\n{label}", fontsize=8)
                if column_index == 0:
                    axis.set_ylabel(f"sigma ratio {ratio:g}", fontsize=10)
    fig.suptitle("How the assumed noise scale changes FLOWER's measurement correction", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output / "figure5_internal_states.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summary = load_csv(args.input / "summary.csv")
    expected_rows = 2 * 5 * 5
    if len(summary) != expected_rows:
        raise ValueError(f"Expected {expected_rows} summary rows, found {len(summary)}")
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    figure1(summary, args.output)
    qualitative_figure(
        args.input,
        summary,
        dataset="celeba",
        output_path=args.output / "figure2_celeba_qualitative.png",
    )
    qualitative_figure(
        args.input,
        summary,
        dataset="afhq_cat",
        output_path=args.output / "figure3_afhq_qualitative.png",
    )
    figure4(args.input, args.output)
    figure5(args.input, args.output)
    print(f"Wrote five figures to {args.output}")


if __name__ == "__main__":
    main()
