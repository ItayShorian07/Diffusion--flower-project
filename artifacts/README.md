# FLOWER robustness project deliverables

The final report, presentation, figures, problem statement, and completed experimental results are organized here. All deliverables use the completed experiment; rebuilding them does not run reconstruction again.

| Folder or file | Contents |
|---|---|
| `report/FLOWER_Noise_Mismatch_Report.pdf` | Final 25-page English report: expanded derivations, 15 numbered figures, two detail continuations, result tables, discussion, and conclusions |
| `report/FLOWER_Noise_Mismatch_Report.tex` | Editable final source; references the figures in `figures/publication/` |
| `presentation/FLOWER_Noise_Mismatch_Presentation.pptx` | Final editable 20-slide presentation with matched crops and six native quantitative charts |
| `presentation/FLOWER_Noise_Mismatch_Presentation.pdf` | Final PDF viewing copy of the presentation |
| `figures/publication/` | Redesigned PNG figures, vector SVG quantitative plots, and source-data hashes |
| `experiments/main/` | All completed numerical results and saved image outputs |
| `problem_statement.md` | Research question, scope, experimental design, and evaluation plan |
| `figures/publication/details/` | Selected detail panels continuing Figures 5–6, using the same crop across every noise ratio |
| `delivery/FLOWER_Noise_Mismatch_Project.zip` | Current local submission bundle with final files, results, figures, sources, and code |
| `delivery/manifest.json` | Versioned final-file hashes and validation counts |

There is one final report and one final presentation. Earlier versions and their obsolete generators have been removed from the working tree. Previously committed versions remain recoverable through Git history.

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
.venv/bin/python tools/build_report_detail_crops.py
.venv/bin/python tools/build_report.py
```

To compile the final report directly, run from `artifacts/report/`:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error FLOWER_Noise_Mismatch_Report.tex
```

The Python dependencies are in `requirements-deliverables.txt`. The report builder uses the committed final LaTeX source, including the detailed derivations and the LPIPS convention in Section 4.3 and Appendix B. The two detail panels follow the full Figures 5–6 without replacing them or changing figure numbers. Numbers below crops remain full-image PSNR values.

Presentation authoring uses `tools/build_presentation.mjs`, `tools/presentation_content.mjs`, the configured Codex artifact runtime, and Roboto Condensed. `FLOWER_ARTIFACT_RUNTIME` and `FLOWER_PRESENTATION_SKILL_DIR` can override the local runtime paths. The builder creates the complete current deck from the completed CSVs and saved images. It does not load an earlier deck. Native chart confidence intervals, embedded workbooks, tables, and explicit image crops are validated before export.

```bash
node tools/build_presentation.mjs
.venv/bin/python tools/validate_and_package_deliverables.py
```

The ZIP is generated locally and intentionally not committed, since its files are already available individually in the repository. The versioned manifest documents the validated final files and source-data hashes.

## Final presentation content

The presentation retains the blue 4:3 design and 20-slide order. The experiment supplies deliberately incorrect assumed noise standard deviations; true measurement noise is known to the experimenter and stays fixed within each paired comparison. Slide 5 makes the controlled variables and `gamma = 0` explicit and defines paired changes before the first graph. Slides 11–15 add approximately 3× matched detail crops across every ratio and both datasets. Their numerical labels report full-image metrics. Slide 18 presents possible explanations, and slide 19 answers the research question directly.
