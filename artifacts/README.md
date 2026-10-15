# FLOWER robustness project deliverables

The current report, presentation, figures, problem statement, and completed experimental results are organized here. The October 15 redesign uses the existing results and does not run reconstruction again.

| Folder or file | Contents |
|---|---|
| `report/robust-flower-report.pdf` | English academic report with the method, mathematical arguments, protocol, all 15 redesigned figures, result tables, discussion, and conclusions |
| `report/robust-flower-report.tex` | Generated LaTeX source; rebuild with the scripts below |
| `presentation/robust-flower-results.pptx` | Editable 20-slide results presentation matching the supplied blue, 4:3 reference style |
| `presentation/robust-flower-results.pdf` | PDF viewing copy of the presentation |
| `figures/publication/` | Redesigned PNG figures, vector SVG quantitative plots, and source-data hashes |
| `experiments/main/` | All completed numerical results and saved image outputs |
| `problem_statement.md` | Research question, scope, experimental design, and evaluation plan |
| `delivery/Robust_FLOWER_Project.zip` | Portable package of the current deliverables and completed results, generated locally |

## Experimental results

The numerical source of truth is `experiments/main/metrics.csv`, containing 1,000 unique image–task–ratio rows. `metrics_with_deltas.csv` adds paired changes from the same-image ratio-1 control. `summary.csv` and `summary.json` contain all 50 groups, each with 20 images, mean metrics, and approximate confidence intervals. `run_metadata.json` records the protocol and seeds.

`reconstructions/` contains the saved fixed qualitative example for every dataset–task combination and every ratio. `analysis_capture/` contains the selected trajectory and three-step diagnostic images. These folders contain every image saved by the completed run; they do not contain a PNG for every one of the 1,000 numerical rows.

## Figure guide

1. `01_psnr_response`: mean paired PSNR differences, with approximate 95% confidence intervals.
2. `02_ssim_response`: the corresponding SSIM response.
3. `03_lpips_response`: the corresponding LPIPS response; lower is better.
4. `04_psnr_mismatch_map`: mean PSNR changes for every task and mismatched ratio.
5. `05_celeba_reconstructions`: all five tasks and all ratios for the saved CelebA example.
6. `06_afhq_cat_reconstructions`: the equivalent AFHQ-Cat comparison.
7. `07_reconstruction_trajectory`: flow time across columns and assumed noise ratio across rows.
8. `08_internal_states_t075`: destination, refinement, and next state at flow time 0.75.
9. `09_internal_states_t025`: the same diagnostic at time 0.25.
10. `10_internal_states_t05`: the same diagnostic at time 0.50.
11–15. `task_*`: a separate PSNR/SSIM/LPIPS comparison for each inverse problem.

Ratios always refer to standard deviation, not variance. The ratio 0.5 corresponds to one quarter of the true variance. Error bars reproduce the stored normal approximation, mean ± 1.96 × standard error of paired differences across 20 images.

## Rebuild without running experiments

From the repository root:

```bash
.venv/bin/python tools/redesign_figures.py
python3 tools/build_academic_report.py
```

The figure builder requires Matplotlib, NumPy, and Pillow. The report builder requires a TeX installation and reads the generated vector figure PDFs from the private build folder. Presentation authoring uses `tools/redesign_presentation.mjs`, the configured artifact runtime, and the reference Roboto Condensed font. Finalization includes native chart confidence intervals and embedded chart data.

The original October 14 DOCX, PPTX, and five benchmark-export figures remain available under their original filenames for comparison. The files listed above are the current version.
