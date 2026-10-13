#!/usr/bin/env python3
"""Re-run one reproducibly selected case and capture FLOWER internal states."""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("TORCH_HOME", str(PROJECT_ROOT / ".cache/torch"))

from robust_flower.benchmark import image_transform, load_image, read_manifest, save_tensor_image
from robust_flower.modeling import load_official_model, resolve_device
from robust_flower.noise import add_gaussian_noise, cpu_generator
from robust_flower.operators import build_operator
from robust_flower.solver import FlowerInverseSolver


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config/robustness.json")
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "artifacts/experiments/main")
    parser.add_argument("--device", default="auto")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text())
    paired_path = args.input / "metrics_with_deltas.csv"
    with paired_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Run the benchmark and summarize_results.py first")

    setting_scores: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        if float(row["assumed_to_true_sigma"]) != 1.0:
            setting_scores[(row["dataset"], row["task"])].append(
                abs(float(row["psnr_delta_vs_correct"]))
            )
    selected_setting = max(
        setting_scores,
        key=lambda key: statistics.mean(setting_scores[key]),
    )
    dataset_name, task_name = selected_setting

    image_scores: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        if (
            row["dataset"] == dataset_name
            and row["task"] == task_name
            and float(row["assumed_to_true_sigma"]) != 1.0
        ):
            image_scores[int(row["image_position"])].append(
                abs(float(row["psnr_delta_vs_correct"]))
            )
    mean_image_scores = {
        position: statistics.mean(values) for position, values in image_scores.items()
    }
    median_score = statistics.median(mean_image_scores.values())
    image_position = min(
        mean_image_scores,
        key=lambda position: (abs(mean_image_scores[position] - median_score), position),
    )

    matching_row = next(
        row
        for row in rows
        if row["dataset"] == dataset_name
        and row["task"] == task_name
        and int(row["image_position"]) == image_position
    )
    dataset_config = config["datasets"][dataset_name]
    task_config = config["tasks"][task_name]
    device = resolve_device(args.device)
    image_size = int(dataset_config["image_size"])
    paths = read_manifest(
        PROJECT_ROOT / dataset_config["image_manifest"],
        PROJECT_ROOT / dataset_config["dataset_root"],
        int(config["image_count_per_dataset"]),
    )
    transform = image_transform(
        dataset_name,
        image_size=image_size,
        center_crop=dataset_config.get("center_crop"),
    )
    clean = load_image(paths[image_position], transform, device)
    operator = build_operator(
        task_name,
        task_config,
        dataset_name=dataset_name,
        image_size=image_size,
        mask_seed=int(config["mask_seed"]),
        device=device,
    )
    true_sigma = float(task_config["true_sigma"])
    clean_measurement = operator.forward(clean)
    measurement, _ = add_gaussian_noise(
        clean_measurement,
        torch.full_like(clean_measurement, true_sigma**2),
        generator=cpu_generator(int(matching_row["measurement_seed"])),
    )

    ratios = [float(value) for value in config["scale_factors"]]
    model = load_official_model(
        PROJECT_ROOT / dataset_config["checkpoint"],
        image_size=image_size,
        device=device,
    )
    solver = FlowerInverseSolver(
        model,
        operator,
        steps=int(dataset_config["steps"][task_name]),
        gamma=int(config["gamma"]),
        cg_max_iterations=int(config["cg_max_iterations"]),
        cg_tolerance=float(config["cg_tolerance"]),
    )
    result = solver.reconstruct(
        measurement.expand(len(ratios), -1, -1, -1),
        torch.tensor([true_sigma * ratio for ratio in ratios], device=device),
        seed=int(matching_row["solver_seed"]),
        shared_noise_across_batch=True,
        capture_times=(0.2, 0.4, 0.6, 0.8, 1.0),
        capture_internal_times=(0.25, 0.5, 0.75),
    )

    output = args.input / "analysis_capture"
    save_tensor_image(clean, output / "ground_truth.png")
    save_tensor_image(operator.adjoint(measurement), output / "measurement.png")
    for time_value, batch in (result.trajectory or {}).items():
        for index, ratio in enumerate(ratios):
            save_tensor_image(
                batch[index : index + 1],
                output / "trajectory" / f"ratio_{ratio:g}" / f"t_{time_value:g}.png",
            )
    internal_ratios = {0.5, 1.0, 1.5}
    for time_value, states in (result.internals or {}).items():
        for index, ratio in enumerate(ratios):
            if ratio not in internal_ratios:
                continue
            for state_name, batch in states.items():
                save_tensor_image(
                    batch[index : index + 1],
                    output
                    / "internals"
                    / f"ratio_{ratio:g}"
                    / f"t_{time_value:g}"
                    / f"{state_name}.png",
                )

    metadata = {
        "selection_rule": "setting with highest mean absolute paired PSNR delta; image closest to the median image-level sensitivity",
        "dataset": dataset_name,
        "task": task_name,
        "image_position": image_position,
        "paper_index": int(matching_row["paper_index"]),
        "image": matching_row["image"],
        "setting_mean_absolute_psnr_delta": statistics.mean(setting_scores[selected_setting]),
        "image_mean_absolute_psnr_delta": mean_image_scores[image_position],
        "median_image_score": median_score,
        "trajectory_times": [0.2, 0.4, 0.6, 0.8, 1.0],
        "internal_times": [0.25, 0.5, 0.75],
        "internal_ratios": [0.5, 1.0, 1.5],
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
