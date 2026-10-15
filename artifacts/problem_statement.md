# Robust FLOWER Under Noise Model Mismatch

## Research question

How does FLOWER reconstruction quality change when the Gaussian measurement-noise standard deviation supplied to the solver is incorrect? Does sensitivity depend on the inverse problem, the image domain, or the reconstruction metric?

## Measurement and reconstruction assumptions

Measurements follow `y = Hx + n`, with `n ~ N(0, sigma_true^2 I)`. Each fixed measurement is reconstructed using `sigma_assumed = r * sigma_true`, where `r` is one of `0.5, 0.75, 1.0, 1.25, 1.5`. These are standard-deviation ratios. The associated variance ratios are `0.25, 0.5625, 1.0, 1.5625, 2.25`.

The matched condition `r = 1` is the control for every image–task pair. The same clean image, observation, forward operator, and source-noise draws are reused across all five conditions.

## Completed experimental design

- Two datasets: CelebA at 128 × 128 and AFHQ-Cat at 256 × 256.
- Twenty fixed images from each dataset's paper benchmark pool, selected with seed 2026.
- Five tasks: denoising, Gaussian deblurring, super-resolution, random inpainting, and box inpainting.
- Five assumed noise ratios per image and task.
- Total: 2 × 20 × 5 × 5 = 1,000 reconstructions.

The degradation parameters, released checkpoints, and iteration counts are recorded in `config/robustness.json`. Selected filenames are recorded in `data_splits/`.

## Evaluation

For each metric M, compute the paired difference `delta_M_i(r) = M_i(r) - M_i(1)`. Report means across the 20 images and approximate 95% intervals using `mean ± 1.96 * SD / sqrt(20)`.

- PSNR: higher is better; changes are measured in dB.
- SSIM: higher is better.
- LPIPS: lower is better; preserve and document the paper-code input convention.

Use fixed qualitative examples and stored trajectories to interpret the numeric response. Use published 100-image paper averages for context, while keeping the paired 20-image control as the baseline for mismatch conclusions.

## Interpretation

The study measures the impact of deliberately misspecified likelihood precision. Its conclusions should distinguish practical effect size from uncertainty, aggregate results from individual examples, and metric agreement from perceptual–distortion trade-offs. An empirically favorable ratio on this test sample is not a universal calibration rule.

All completed numerical results are in `artifacts/experiments/main/`. The redesigned report and figures use these existing files without new reconstruction runs.
