# FLOWER Under Noise Scale Mismatch

This repository studies how the original FLOWER inverse-problem solver behaves when the reconstruction algorithm receives an incorrect Gaussian measurement-noise standard deviation. It evaluates the released model and reconstruction rule without introducing another method.

[Download the Kaggle benchmark notebook](notebooks/run_full_benchmark_kaggle.ipynb) or [open the Google Colab version](https://colab.research.google.com/github/ItayShorian07/Diffusion--flower-project/blob/main/notebooks/run_full_benchmark_colab.ipynb).

## Research question

Measurements follow

\[
y = Hx + n, \qquad n \sim \mathcal N(0, \sigma_{\mathrm{true}}^2 I).
\]

FLOWER reconstructs the same measurement five times with

\[
\frac{\sigma_{\mathrm{assumed}}}{\sigma_{\mathrm{true}}}
\in \{0.5, 0.75, 1, 1.25, 1.5\}.
\]

The ratio multiplies the standard deviation. The corresponding assumed-to-true variance ratios are \(0.25, 0.5625, 1, 1.5625, 2.25\). The covariance shape remains correct and fixed, so the experiment isolates noise-scale misspecification.

## Experimental protocol

The benchmark uses two datasets and all five inverse problems reported in the FLOWER paper.

| Dataset | Images | Resolution | Sampling rule |
|---|---:|---:|---|
| CelebA | 20 | 128 x 128 | Fixed random sample from the paper-ordered first 100 test images |
| AFHQ-Cat | 20 | 256 x 256 | Fixed random sample from the paper-ordered first 100 test images |

The sample seed is 2026. The selected zero-based positions are recorded in `data_splits/random20_seed2026.json`. The same images appear in every task and every noise condition.

| Inverse problem | Measurement operator | True noise standard deviation | Dataset-specific parameter |
|---|---|---:|---|
| Gaussian denoising | Identity | 0.20 | None |
| Gaussian deblurring | Circular Gaussian blur | 0.05 | Blur sigma 1.0 on CelebA and 3.0 on AFHQ-Cat |
| Super-resolution | Decimation | 0.05 | 2x on CelebA and 4x on AFHQ-Cat |
| Random inpainting | Fixed Bernoulli mask | 0.01 | 70 percent missing, mask seed 42 |
| Box inpainting | Fixed centered mask | 0.05 | 40 x 40 on CelebA and 80 x 80 on AFHQ-Cat |

For each image and task, the code generates one measurement and reuses it across all five assumed noise levels. The operator, mask or blur kernel, measurement-noise realization, model weights, and FLOWER source-noise trajectory also remain fixed. The control condition is the ratio 1.0.

The full experiment contains 1,000 reconstructions:

\[
2\text{ datasets} \times 5\text{ tasks} \times 20\text{ images} \times 5\text{ ratios}.
\]

The configuration preserves the public paper scripts' FLOWER step counts: 100 steps for every CelebA task; for AFHQ-Cat, 100 steps for denoising and box inpainting, 200 for random inpainting, and 500 for deblurring and super-resolution.

## Metrics and figures

The evaluation uses the public FLOWER conventions for PSNR, SSIM, and LPIPS. The primary paired statistic is

\[
\Delta \mathrm{PSNR}_i(r)
=
\mathrm{PSNR}_i(r)-\mathrm{PSNR}_i(1).
\]

The plotting script creates exactly five figures:

1. Mean paired PSNR change with 95 percent confidence intervals for every task and dataset.
2. CelebA final reconstructions for the most and least sensitive tasks.
3. AFHQ-Cat final reconstructions for the most and least sensitive tasks.
4. FLOWER trajectories at \(t=0.2,0.4,0.6,0.8,1.0\) for a reproducibly selected case.
5. The prior destination, measurement-refined destination, and next trajectory state at three times and three noise ratios.

The full 50-row results table contains both datasets, five tasks, and five ratios. The analysis case uses the setting with the largest mean absolute paired PSNR change and the image closest to the median image-level sensitivity.

## Run on Kaggle

Kaggle is the recommended free route because **Save Version > Save & Run All** executes the notebook as a background version run and preserves files written to `/kaggle/working` as notebook outputs. Import `notebooks/run_full_benchmark_kaggle.ipynb`, enable a GPU and Internet in the notebook options, then select **Save Version > Save & Run All**. The final output is `robust_flower_results.zip`.

The notebook validates CUDA, clones this repository, downloads the two official checkpoints and only the selected benchmark images, runs all 1,000 reconstructions, builds the aggregate tables and five figures, validates the row and figure counts, and packages the result.

## Run on Google Colab

The Colab notebook is the recommended route because the paper-aligned AFHQ experiments use up to 500 model evaluations per reconstruction. Open the badge above, select a T4 GPU, and run all cells. The notebook:

- checks that CUDA is available;
- mounts Google Drive;
- downloads only the two required FLOWER checkpoints;
- downloads the official datasets and extracts only the selected 20 images per dataset;
- resumes completed rows after a disconnect;
- writes raw metrics, aggregate tables, reconstructions, internal states, and figures to `MyDrive/RobustFLOWER`.

## Run locally

Create an environment and install the dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-robustness.txt
```

Download the two official checkpoints and prepare the 40 selected images:

```bash
bash scripts/download_benchmark_models.sh
bash scripts/prepare_benchmark_data.sh
```

Run and analyze the benchmark:

```bash
.venv/bin/python experiments/run_noise_mismatch.py --device cuda
.venv/bin/python experiments/summarize_results.py
.venv/bin/python experiments/capture_analysis.py --device cuda
.venv/bin/python experiments/plot_results.py
```

The runner writes each completed image-task batch immediately. Run the same command again to resume. Use `--quick` only for a smoke test; its outputs are not valid final results.

## Repository structure

```text
config/robustness.json                 Complete experimental protocol
data_splits/                           Fixed image manifests and selection metadata
experiments/run_noise_mismatch.py      Paired GPU benchmark with resume support
experiments/summarize_results.py       Per-image deltas, means, and confidence intervals
experiments/capture_analysis.py        Reproducible trajectory and internal-state capture
experiments/plot_results.py            The five predefined paper-style figures
notebooks/run_full_benchmark_colab.ipynb
notebooks/run_full_benchmark_kaggle.ipynb
robust_flower/                          Solver, operators, metrics, data, and model loading
scripts/                                Minimal data and checkpoint preparation
tests/                                  Determinism, adjoint, refinement, and capture tests
tools/                                  English report and presentation builders
```

## Validation

```bash
.venv/bin/pytest -q
```

The tests verify deterministic corruption, paired solver randomness, operator adjoints, closed-form Gaussian refinements, super-resolution dimensions, and trajectory capture.

## Source and attribution

This project builds on [FLOWER: A Flow-Matching Solver for Inverse Problems](https://openreview.net/forum?id=QGd34p02mI) by Mehrsa Pourya, Bassam El Rawas, and Michael Unser and the [official FLOWER repository](https://github.com/mehrsapo/Flower). The retained `pnpflow/models.py` file provides the official UNet architecture needed to load the released checkpoints. Dataset files and model weights are downloaded at runtime and are not committed to this repository.
