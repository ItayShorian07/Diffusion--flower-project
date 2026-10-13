#!/usr/bin/env python3
"""Run the paired 20+20 image FLOWER sigma-mismatch benchmark."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("TORCH_HOME", str(PROJECT_ROOT / ".cache/torch"))

from robust_flower.benchmark import image_transform, load_image, read_manifest, save_tensor_image
from robust_flower.metrics import MetricEvaluator
from robust_flower.modeling import load_official_model, resolve_device
from robust_flower.noise import add_gaussian_noise, cpu_generator
from robust_flower.operators import build_operator
from robust_flower.solver import FlowerInverseSolver


CSV_FIELDS = [
    "dataset",
    "task",
    "image",
    "image_position",
    "paper_index",
    "measurement_seed",
    "solver_seed",
    "steps",
    "true_sigma",
    "assumed_sigma",
    "assumed_to_true_sigma",
    "assumed_to_true_variance",
    "psnr",
    "ssim",
    "lpips",
    "measurement_psnr",
    "measurement_ssim",
    "measurement_lpips",
    "runtime_seconds",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config/robustness.json")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "artifacts/experiments/main")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--datasets", nargs="+", choices=["celeba", "afhq_cat"])
    parser.add_argument("--tasks", nargs="+")
    parser.add_argument("--image-batch-size", type=int, default=1)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--end-index", type=int)
    parser.add_argument("--torch-threads", type=int)
    parser.add_argument("--max-steps", type=int, help="Cap steps for a diagnostic run only")
    parser.add_argument("--skip-lpips", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="One image, all tasks, ratios {0.5,1,1.5}, at most two steps",
    )
    return parser.parse_args()


def read_completed(path: Path) -> tuple[list[dict[str, Any]], set[tuple[str, str, int, float]]]:
    if not path.is_file():
        return [], set()
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != CSV_FIELDS:
            raise ValueError("Existing metrics.csv uses another schema; use --overwrite")
        rows = list(reader)
    completed = {
        (
            row["dataset"],
            row["task"],
            int(row["image_position"]),
            float(row["assumed_to_true_sigma"]),
        )
        for row in rows
    }
    return rows, completed


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row["dataset"]),
            str(row["task"]),
            int(row["image_position"]),
            float(row["assumed_to_true_sigma"]),
        ),
    )
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ordered)


def reset_output(output: Path) -> None:
    if not output.exists():
        return
    for name in ("metrics.csv", "summary.csv", "summary.json", "run_metadata.json"):
        candidate = output / name
        if candidate.exists():
            candidate.unlink()
    reconstructions = output / "reconstructions"
    if reconstructions.exists():
        shutil.rmtree(reconstructions)


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text())
    dataset_names = args.datasets or list(config["datasets"])
    task_names = args.tasks or list(config["tasks"])
    unknown_tasks = set(task_names) - set(config["tasks"])
    if unknown_tasks:
        raise ValueError(f"Unknown tasks: {sorted(unknown_tasks)}")
    if args.image_batch_size <= 0 or args.start_index < 0:
        raise ValueError("batch size must be positive and start index non-negative")
    if args.torch_threads is not None:
        torch.set_num_threads(args.torch_threads)
        torch.set_num_interop_threads(1)
    ratios = [float(value) for value in config["scale_factors"]]
    if args.quick:
        ratios = [0.5, 1.0, 1.5]
        args.end_index = min(args.end_index or 1, 1)
        args.max_steps = 2

    output = args.output
    if args.overwrite:
        reset_output(output)
    output.mkdir(parents=True, exist_ok=True)
    metrics_path = output / "metrics.csv"
    rows, completed = read_completed(metrics_path)
    selection = json.loads((PROJECT_ROOT / "data_splits/random20_seed2026.json").read_text())
    paper_indices = selection["zero_based_paper_indices"]
    device = resolve_device(args.device)
    evaluator = MetricEvaluator(
        device=device,
        enable_lpips=not args.skip_lpips,
        paper_compatible=True,
    )
    print(f"Device: {device}; datasets={dataset_names}; tasks={task_names}", flush=True)

    metadata = {
        "config": config,
        "device": str(device),
        "torch_version": torch.__version__,
        "lpips_enabled": not args.skip_lpips,
        "paired_conditions": True,
        "pairing": "same image, measurement, H, mask/kernel, and FLOWER source-noise trajectory across ratios",
        "sigma_ratio_definition": "assumed standard deviation / true standard deviation",
        "variance_ratio_definition": "sigma_ratio squared",
        "selected_paper_indices_zero_based": paper_indices,
        "requested_datasets": dataset_names,
        "requested_tasks": task_names,
        "max_steps_override": args.max_steps,
        "completed_rows": len(rows),
    }
    (output / "run_metadata.json").write_text(json.dumps(metadata, indent=2))

    total_requested = len(dataset_names) * len(task_names) * (
        (args.end_index or config["image_count_per_dataset"]) - args.start_index
    ) * len(ratios)
    dataset_order = list(config["datasets"])
    task_order = list(config["tasks"])

    for dataset_name in dataset_names:
        dataset_config = config["datasets"][dataset_name]
        image_size = int(dataset_config["image_size"])
        checkpoint = PROJECT_ROOT / dataset_config["checkpoint"]
        model = load_official_model(checkpoint, image_size=image_size, device=device)
        transform = image_transform(
            dataset_name,
            image_size=image_size,
            center_crop=dataset_config.get("center_crop"),
        )
        image_paths = read_manifest(
            PROJECT_ROOT / dataset_config["image_manifest"],
            PROJECT_ROOT / dataset_config["dataset_root"],
            int(config["image_count_per_dataset"]),
        )
        end_index = len(image_paths) if args.end_index is None else args.end_index
        if end_index < args.start_index or end_index > len(image_paths):
            raise ValueError("invalid --start-index/--end-index range")
        indexed_paths = list(enumerate(image_paths))[args.start_index:end_index]

        for task_name in task_names:
            task_config = config["tasks"][task_name]
            operator = build_operator(
                task_name,
                task_config,
                dataset_name=dataset_name,
                image_size=image_size,
                mask_seed=int(config["mask_seed"]),
                device=device,
            )
            paper_steps = int(dataset_config["steps"][task_name])
            steps = min(paper_steps, args.max_steps) if args.max_steps else paper_steps
            solver = FlowerInverseSolver(
                model,
                operator,
                steps=steps,
                gamma=int(config["gamma"]),
                cg_max_iterations=int(config["cg_max_iterations"]),
                cg_tolerance=float(config["cg_tolerance"]),
            )
            true_sigma = float(task_config["true_sigma"])

            pending = [
                (position, path)
                for position, path in indexed_paths
                if any(
                    (dataset_name, task_name, position, ratio) not in completed
                    for ratio in ratios
                )
            ]
            for chunk_start in range(0, len(pending), args.image_batch_size):
                chunk = pending[chunk_start : chunk_start + args.image_batch_size]
                cases: list[dict[str, Any]] = []
                for position, image_path in chunk:
                    clean = load_image(image_path, transform, device)
                    clean_measurement = operator.forward(clean)
                    dataset_offset = dataset_order.index(dataset_name) * 100000
                    task_offset = task_order.index(task_name) * 1000
                    measurement_seed = int(config["measurement_seed"]) + dataset_offset + task_offset + position
                    solver_seed = int(config["solver_seed"]) + dataset_offset + task_offset + position
                    variance = torch.full_like(clean_measurement, true_sigma**2)
                    measurement, _ = add_gaussian_noise(
                        clean_measurement,
                        variance,
                        generator=cpu_generator(measurement_seed),
                    )
                    pending_ratios = [
                        ratio
                        for ratio in ratios
                        if (dataset_name, task_name, position, ratio) not in completed
                    ]
                    cases.append(
                        {
                            "position": position,
                            "path": image_path,
                            "clean": clean,
                            "measurement": measurement,
                            "measurement_seed": measurement_seed,
                            "solver_seed": solver_seed,
                            "ratios": pending_ratios,
                        }
                    )

                expanded_measurements: list[torch.Tensor] = []
                expanded_clean: list[torch.Tensor] = []
                expanded_sigmas: list[float] = []
                noise_groups: list[tuple[torch.Generator, int]] = []
                measurement_displays: list[torch.Tensor] = []
                for case in cases:
                    count = len(case["ratios"])
                    expanded_measurements.append(case["measurement"].expand(count, -1, -1, -1))
                    expanded_clean.append(case["clean"].expand(count, -1, -1, -1))
                    expanded_sigmas.extend(true_sigma * ratio for ratio in case["ratios"])
                    noise_groups.append((cpu_generator(case["solver_seed"]), count))
                    measurement_displays.append(operator.adjoint(case["measurement"]))

                started = time.perf_counter()
                result = solver.reconstruct(
                    torch.cat(expanded_measurements, dim=0),
                    torch.tensor(expanded_sigmas, device=device),
                    noise_groups=noise_groups,
                )
                runtime = time.perf_counter() - started
                reconstruction_metrics = evaluator.evaluate_each(
                    torch.cat(expanded_clean, dim=0), result.image
                )
                measurement_metrics = evaluator.evaluate_each(
                    torch.cat([case["clean"] for case in cases], dim=0),
                    torch.cat(measurement_displays, dim=0),
                )

                offset = 0
                for case, degraded_metrics, degraded_display in zip(
                    cases, measurement_metrics, measurement_displays
                ):
                    position = int(case["position"])
                    ratios_for_image = case["ratios"]
                    if position == int(config["qualitative_sample_position"]):
                        qualitative_dir = (
                            output
                            / "reconstructions"
                            / dataset_name
                            / task_name
                            / f"image_{position:02d}_{case['path'].stem}"
                        )
                        save_tensor_image(case["clean"], qualitative_dir / "ground_truth.png")
                        save_tensor_image(degraded_display, qualitative_dir / "measurement.png")

                    per_reconstruction_runtime = runtime / max(1, result.image.shape[0])
                    for local_index, ratio in enumerate(ratios_for_image):
                        metric = reconstruction_metrics[offset + local_index]
                        row = {
                            "dataset": dataset_name,
                            "task": task_name,
                            "image": case["path"].name,
                            "image_position": position,
                            "paper_index": paper_indices[position],
                            "measurement_seed": case["measurement_seed"],
                            "solver_seed": case["solver_seed"],
                            "steps": steps,
                            "true_sigma": true_sigma,
                            "assumed_sigma": true_sigma * ratio,
                            "assumed_to_true_sigma": ratio,
                            "assumed_to_true_variance": ratio**2,
                            **metric,
                            "measurement_psnr": degraded_metrics["psnr"],
                            "measurement_ssim": degraded_metrics["ssim"],
                            "measurement_lpips": degraded_metrics["lpips"],
                            "runtime_seconds": per_reconstruction_runtime,
                        }
                        rows.append(row)
                        completed.add((dataset_name, task_name, position, ratio))
                        if position == int(config["qualitative_sample_position"]):
                            save_tensor_image(
                                result.image[offset + local_index : offset + local_index + 1],
                                qualitative_dir / f"sigma_ratio_{ratio:g}.png",
                            )
                        print(
                            f"[{len(rows)}/{total_requested}] {dataset_name}/{task_name} "
                            f"image={position:02d} ratio={ratio:g} PSNR={metric['psnr']:.3f}",
                            flush=True,
                        )
                    offset += len(ratios_for_image)

                write_rows(metrics_path, rows)
                metadata["completed_rows"] = len(rows)
                (output / "run_metadata.json").write_text(json.dumps(metadata, indent=2))

            del solver, operator
        del model

    print(f"Saved {len(rows)} rows to {metrics_path}")


if __name__ == "__main__":
    main()
