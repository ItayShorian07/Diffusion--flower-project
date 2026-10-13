#!/usr/bin/env python3
"""Aggregate paired FLOWER mismatch results and compute confidence intervals."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev


METRICS = ("psnr", "ssim", "lpips")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("artifacts/experiments/main/metrics.csv"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/experiments/main"))
    return parser.parse_args()


def ci95(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return 0.0 if len(finite) < 2 else 1.96 * stdev(finite) / math.sqrt(len(finite))


def main() -> None:
    args = parse_args()
    with args.input.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("No metric rows found")

    controls = {
        (row["dataset"], row["task"], int(row["image_position"])): row
        for row in rows
        if float(row["assumed_to_true_sigma"]) == 1.0
    }
    expected_controls = {
        (row["dataset"], row["task"], int(row["image_position"])) for row in rows
    }
    missing = expected_controls - set(controls)
    if missing:
        raise ValueError(f"Missing ratio=1 control for {len(missing)} image/task pairs")

    paired_rows: list[dict[str, str | float]] = []
    for row in rows:
        control = controls[(row["dataset"], row["task"], int(row["image_position"]))]
        enriched: dict[str, str | float] = dict(row)
        for metric in METRICS:
            enriched[f"{metric}_delta_vs_correct"] = float(row[metric]) - float(control[metric])
        paired_rows.append(enriched)

    groups: dict[tuple[str, str, float], list[dict[str, str | float]]] = defaultdict(list)
    for row in paired_rows:
        groups[(row["dataset"], row["task"], float(row["assumed_to_true_sigma"]))].append(row)

    summary: list[dict[str, str | int | float]] = []
    for (dataset, task, ratio), group in groups.items():
        record: dict[str, str | int | float] = {
            "dataset": dataset,
            "task": task,
            "assumed_to_true_sigma": ratio,
            "assumed_to_true_variance": ratio**2,
            "n": len(group),
            "true_sigma": mean(float(row["true_sigma"]) for row in group),
            "steps": int(round(mean(float(row["steps"]) for row in group))),
        }
        for metric in METRICS:
            values = [float(row[metric]) for row in group]
            deltas = [float(row[f"{metric}_delta_vs_correct"]) for row in group]
            record[f"{metric}_mean"] = mean(values)
            record[f"{metric}_ci95"] = ci95(values)
            record[f"{metric}_delta_vs_correct_mean"] = mean(deltas)
            record[f"{metric}_delta_vs_correct_ci95"] = ci95(deltas)
        summary.append(record)

    dataset_order = {"celeba": 0, "afhq_cat": 1}
    task_order = {
        "denoising": 0,
        "gaussian_deblurring": 1,
        "super_resolution": 2,
        "random_inpainting": 3,
        "box_inpainting": 4,
    }
    summary.sort(
        key=lambda row: (
            dataset_order.get(str(row["dataset"]), 99),
            task_order.get(str(row["task"]), 99),
            float(row["assumed_to_true_sigma"]),
        )
    )

    sensitivities = []
    for dataset in dataset_order:
        for task in task_order:
            mismatch = [
                abs(float(row["psnr_delta_vs_correct_mean"]))
                for row in summary
                if row["dataset"] == dataset
                and row["task"] == task
                and float(row["assumed_to_true_sigma"]) != 1.0
            ]
            if mismatch:
                sensitivities.append(
                    {
                        "dataset": dataset,
                        "task": task,
                        "mean_absolute_psnr_delta": mean(mismatch),
                    }
                )
    sensitivities.sort(key=lambda row: float(row["mean_absolute_psnr_delta"]), reverse=True)

    args.output.mkdir(parents=True, exist_ok=True)
    paired_path = args.output / "metrics_with_deltas.csv"
    with paired_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(paired_rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(paired_rows)
    summary_path = args.output / "summary.csv"
    with summary_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary)
    (args.output / "summary.json").write_text(
        json.dumps({"summary": summary, "sensitivity_ranking": sensitivities}, indent=2)
    )
    print(f"Wrote {len(summary)} aggregate rows and {len(paired_rows)} paired rows")


if __name__ == "__main__":
    main()
