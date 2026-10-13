import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const ROOT = "/Users/Itays/Diffusion- flower project";
const SKILL_DIR = "/Users/Itays/.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations";
const RUNTIME_PYTHON = "/Users/Itays/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3";
const BUILD_DIR = path.join(ROOT, "artifacts/build/presentation");
const STAGING_DIR = path.join(ROOT, "artifacts/build/presentation-finalizer");
const FINAL_PPTX = path.join(ROOT, "artifacts/presentation/flower-noise-scale-mismatch.pptx");

const {
  resolvePresentationFont,
  applyPresentationChartFont,
  finalizePresentation,
} = await import(pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href);

await fs.mkdir(BUILD_DIR, { recursive: true });
await fs.mkdir(STAGING_DIR, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });

const config = JSON.parse(await fs.readFile(path.join(ROOT, "config/robustness.json"), "utf8"));
const summaryText = await fs.readFile(path.join(ROOT, "artifacts/experiments/main/summary.csv"), "utf8");
const [csvHeader, ...lines] = summaryText.trim().split(/\r?\n/).map((line) => line.split(","));
const rows = lines.map((values) => Object.fromEntries(csvHeader.map((key, index) => [key, values[index]])));
if (rows.length !== 50) throw new Error(`Expected 50 summary rows, found ${rows.length}`);

const datasets = ["celeba", "afhq_cat"];
const datasetLabels = { celeba: "CelebA", afhq_cat: "AFHQ-Cat" };
const tasks = ["denoising", "gaussian_deblurring", "super_resolution", "random_inpainting", "box_inpainting"];
const taskLabels = {
  denoising: "Denoising",
  gaussian_deblurring: "Deblurring",
  super_resolution: "Super-resolution",
  random_inpainting: "Random inpainting",
  box_inpainting: "Box inpainting",
};
const ratios = [0.5, 0.75, 1, 1.25, 1.5];
const byKey = new Map(rows.map((row) => [`${row.dataset}|${row.task}|${Number(row.assumed_to_true_sigma)}`, row]));
const rowFor = (dataset, task, ratio) => byKey.get(`${dataset}|${task}|${ratio}`);
const sensitivity = (dataset, task) => {
  const values = ratios.filter((ratio) => ratio !== 1).map((ratio) => Math.abs(Number(rowFor(dataset, task, ratio).psnr_delta_vs_correct_mean)));
  return values.reduce((sum, value) => sum + value, 0) / values.length;
};
const rankedSettings = datasets.flatMap((dataset) => tasks.map((task) => ({ dataset, task, value: sensitivity(dataset, task) }))).sort((a, b) => b.value - a.value);
const mostSensitive = rankedSettings[0];
const leastSensitive = rankedSettings[rankedSettings.length - 1];

const family = resolvePresentationFont({ fontFamily: "Aptos" });
const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });

const C = {
  navy: "#17324D",
  blue: "#176B87",
  cyan: "#64CCC5",
  coral: "#D45D4C",
  green: "#3B8264",
  purple: "#7758A6",
  gold: "#C68A24",
  ink: "#17212B",
  muted: "#5E6974",
  pale: "#EAF4F8",
  warm: "#F6F1EA",
  grid: "#D9E1E7",
  white: "#FFFFFF",
};
const taskColors = [C.blue, C.gold, C.purple, C.green, C.coral];

function rect(slide, left, top, width, height, fill, lineFill = "none", radius = 0) {
  return slide.shapes.add({
    geometry: radius ? "roundRect" : "rect",
    position: { left, top, width, height },
    fill,
    line: { fill: lineFill, width: lineFill === "none" ? 0 : 1 },
  });
}

function textBox(slide, text, left, top, width, height, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left, top, width, height },
    fill: options.fill ?? "none",
    line: { fill: options.lineFill ?? "none", width: options.lineWidth ?? 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: family,
    fontSize: options.fontSize ?? 22,
    bold: options.bold ?? false,
    color: options.color ?? C.ink,
    alignment: options.alignment ?? "left",
    verticalAlignment: options.verticalAlignment ?? "middle",
    autoFit: options.autoFit ?? "shrinkText",
  };
  return shape;
}

function header(slide, title, number) {
  slide.background.fill = C.white;
  rect(slide, 0, 0, 1280, 9, C.blue);
  textBox(slide, title, 66, 36, 1080, 70, { fontSize: 36, bold: true, color: C.navy });
  textBox(slide, String(number).padStart(2, "0"), 1170, 42, 44, 26, { fontSize: 13, bold: true, color: C.muted, alignment: "right" });
}

function footer(slide, text = "FLOWER measurement noise scale mismatch") {
  rect(slide, 66, 684, 1148, 1, C.grid);
  textBox(slide, text, 66, 689, 760, 16, { fontSize: 10, color: C.muted });
  textBox(slide, "20 CelebA + 20 AFHQ-Cat", 930, 689, 284, 16, { fontSize: 10, color: C.muted, alignment: "right" });
}

function notes(slide, body, sources = []) {
  const sourceText = sources.length ? `\n\nSources:\n${sources.join("\n")}` : "";
  slide.speakerNotes.textFrame.setText(`${body}${sourceText}`);
}

async function bytes(relativePath) {
  return fs.readFile(path.join(ROOT, relativePath));
}

async function addImage(slide, relativePath, position, alt, fit = "contain") {
  slide.images.add({
    blob: await bytes(relativePath),
    contentType: "image/png",
    alt,
    fit,
    position,
  });
}

async function qualitativeDir(dataset, task) {
  const root = path.join(ROOT, "artifacts/experiments/main/reconstructions", dataset, task);
  const names = (await fs.readdir(root)).filter((name) => name.startsWith("image_")).sort();
  if (names.length !== 1) throw new Error(`Expected one qualitative directory for ${dataset}/${task}`);
  return path.join("artifacts/experiments/main/reconstructions", dataset, task, names[0]);
}

function styleChart(chart) {
  applyPresentationChartFont(chart, { fontFamily: family });
  chart.chartFill = C.white;
  chart.plotAreaFill = C.white;
  return chart;
}

function addResultsTable(slide, dataset, left) {
  const values = [["Task", "Our control", "Paper", "Difference"]];
  for (const task of tasks) {
    const ours = Number(rowFor(dataset, task, 1).psnr_mean);
    const paper = Number(config.paper_flower1_ot_reference[dataset][task][0]);
    values.push([taskLabels[task], ours.toFixed(2), paper.toFixed(2), (ours - paper).toFixed(2)]);
  }
  const table = slide.tables.add({
    rows: values.length,
    columns: 4,
    left,
    top: 178,
    width: 548,
    height: 350,
    columnTracks: [
      { mode: "fr", value: 1.8 },
      { mode: "fr", value: 1.0 },
      { mode: "fr", value: 0.9 },
      { mode: "fr", value: 0.9 },
    ],
    values,
  });
  table.styleOptions = { headerRow: true, bandedRows: true };
  table.borders.assign({ style: "solid", fill: C.grid, width: 1 });
  for (let column = 0; column < 4; column += 1) table.getCell(0, column).fill = C.navy;
  table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: 4 }).assign({
    textStyle: { typeface: family, fontSize: 14, bold: true, color: C.white },
    margins: { top: 8, right: 8, bottom: 8, left: 8 },
  });
  table.cells.block({ row: 1, column: 0, rowCount: 5, columnCount: 4 }).assign({
    textStyle: { typeface: family, fontSize: 13, color: C.ink },
    margins: { top: 8, right: 7, bottom: 8, left: 7 },
    anchor: "middle",
  });
  textBox(slide, datasetLabels[dataset], left, 138, 548, 32, { fontSize: 22, bold: true, color: C.blue, alignment: "center" });
}

// Slide 1
{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy;
  const celebDir = await qualitativeDir("celeba", "denoising");
  const afhqDir = await qualitativeDir("afhq_cat", "denoising");
  await addImage(slide, path.join(celebDir, "ground_truth.png"), { left: 820, top: 96, width: 280, height: 280 }, "Selected CelebA image", "cover");
  await addImage(slide, path.join(afhqDir, "ground_truth.png"), { left: 950, top: 330, width: 250, height: 250 }, "Selected AFHQ-Cat image", "cover");
  textBox(slide, "FLOWER Under Measurement\nNoise Scale Mismatch", 72, 112, 680, 176, { fontSize: 51, bold: true, color: C.white });
  textBox(slide, "A paired GPU benchmark across five inverse problems and two image domains", 76, 316, 620, 84, { fontSize: 23, color: "#D5E7EF" });
  textBox(slide, "1,000 reconstructions   PSNR   SSIM   LPIPS", 76, 472, 610, 40, { fontSize: 18, bold: true, color: C.cyan });
  textBox(slide, "Itay Shorian   13 October 2026", 76, 626, 500, 28, { fontSize: 15, color: "#B9CCD6" });
  notes(slide, "The project measures how the original FLOWER solver responds when the Gaussian measurement-noise standard deviation supplied during reconstruction is wrong.", [
    "FLOWER paper: https://openreview.net/forum?id=QGd34p02mI",
    "Official code: https://github.com/mehrsapo/Flower",
  ]);
}

// Slide 2
{
  const slide = presentation.slides.add();
  header(slide, "Research question and paired comparison", 2);
  await addImage(slide, "artifacts/build/report-equations/measurement.png", { left: 88, top: 138, width: 600, height: 90 }, "Gaussian measurement model");
  textBox(slide, "The measurement is generated once", 112, 248, 490, 38, { fontSize: 24, bold: true, color: C.navy });
  textBox(slide, "The operator, noise realization, mask or kernel, model weights, and FLOWER source-noise trajectory remain fixed.", 112, 292, 490, 118, { fontSize: 20, color: C.muted });
  textBox(slide, "Only the assumed standard deviation changes", 112, 438, 490, 38, { fontSize: 24, bold: true, color: C.coral });
  textBox(slide, "0.5     0.75     1.0     1.25     1.5", 100, 492, 520, 54, { fontSize: 29, bold: true, color: C.blue, alignment: "center" });
  rect(slide, 716, 142, 474, 410, C.pale, C.grid, 18);
  textBox(slide, "Paired statistic", 760, 172, 390, 32, { fontSize: 17, bold: true, color: C.blue, alignment: "center" });
  await addImage(slide, "artifacts/build/report-equations/delta-psnr.png", { left: 760, top: 220, width: 390, height: 88 }, "Paired PSNR change equation");
  textBox(slide, "Ratio 1.0 is the correctly specified control for the same image and measurement.", 770, 330, 370, 82, { fontSize: 21, bold: true, color: C.navy, alignment: "center" });
  textBox(slide, "The project evaluates the released model and reconstruction rule. It does not train another model.", 770, 438, 370, 76, { fontSize: 18, color: C.muted, alignment: "center" });
  footer(slide);
  notes(slide, "Pairing isolates the assumed noise scale from changes caused by another measurement draw or another stochastic trajectory.", ["Protocol: config/robustness.json"]);
}

// Slide 3
{
  const slide = presentation.slides.add();
  header(slide, "FLOWER uses three steps at every flow time", 3);
  const steps = [
    ["1", "Prior destination", "The velocity network predicts x-hat-1.", C.blue],
    ["2", "Measurement refinement", "The assumed sigma weights the likelihood.", C.coral],
    ["3", "Time progression", "The refined destination advances the trajectory.", C.green],
  ];
  steps.forEach(([number, label, body, color], index) => {
    const left = 72 + index * 402;
    textBox(slide, number, left, 150, 58, 58, { fontSize: 34, bold: true, color, alignment: "center" });
    textBox(slide, label, left + 70, 148, 300, 40, { fontSize: 23, bold: true, color: C.navy });
    textBox(slide, body, left + 70, 192, 300, 64, { fontSize: 17, color: C.muted });
  });
  await addImage(slide, "artifacts/build/report-equations/flow-path.png", { left: 98, top: 290, width: 690, height: 86 }, "FLOWER path and destination equation");
  await addImage(slide, "artifacts/build/report-equations/proximal-objective.png", { left: 98, top: 410, width: 690, height: 102 }, "Measurement refinement objective");
  rect(slide, 844, 290, 346, 230, C.warm, C.grid, 16);
  textBox(slide, "Where mismatch acts", 878, 310, 278, 30, { fontSize: 19, bold: true, color: C.coral, alignment: "center" });
  textBox(slide, "A smaller assumed sigma strengthens the data term. A larger value gives the learned prior more influence.", 878, 354, 278, 128, { fontSize: 21, bold: true, color: C.navy, alignment: "center" });
  textBox(slide, "The report gives short proofs for the conditional destination, Gaussian refinement, proximal equivalence, and ancestral transition.", 138, 570, 1004, 58, { fontSize: 19, color: C.muted, alignment: "center" });
  footer(slide);
  notes(slide, "Sigma appears directly in Step 2. Later Step 1 predictions can also differ because previous refinements changed the trajectory state.", ["FLOWER paper, Propositions 1 to 3: https://openreview.net/forum?id=QGd34p02mI"]);
}

// Slide 4
{
  const slide = presentation.slides.add();
  header(slide, "Ten settings cover five operators and two domains", 4);
  for (let datasetIndex = 0; datasetIndex < datasets.length; datasetIndex += 1) {
    const dataset = datasets[datasetIndex];
    const top = 150 + datasetIndex * 230;
    textBox(slide, datasetLabels[dataset], 64, top + 62, 120, 40, { fontSize: 22, bold: true, color: C.blue, alignment: "center" });
    for (let taskIndex = 0; taskIndex < tasks.length; taskIndex += 1) {
      const task = tasks[taskIndex];
      const dir = await qualitativeDir(dataset, task);
      const left = 205 + taskIndex * 198;
      await addImage(slide, path.join(dir, "measurement.png"), { left, top, width: 158, height: 158 }, `${datasetLabels[dataset]} ${taskLabels[task]} measurement`, "cover");
      textBox(slide, taskLabels[task], left - 8, top + 164, 174, 34, { fontSize: 13, bold: true, color: C.ink, alignment: "center" });
    }
  }
  textBox(slide, "The same 20 selected images pass through every task within a dataset", 210, 608, 940, 40, { fontSize: 20, bold: true, color: C.navy, alignment: "center" });
  footer(slide);
  notes(slide, "Measurements shown here use the fixed qualitative image in each dataset. The task-specific sigma and operator parameters match the public paper setup.", ["Generated measurements: artifacts/experiments/main/reconstructions"]);
}

// Slide 5
{
  const slide = presentation.slides.add();
  header(slide, "Task parameters match the public FLOWER benchmark", 5);
  const values = [
    ["Task", "True sigma", "CelebA", "AFHQ-Cat"],
    ["Denoising", "0.20", "Identity, 100 steps", "Identity, 100 steps"],
    ["Deblurring", "0.05", "Blur sigma 1, 100 steps", "Blur sigma 3, 500 steps"],
    ["Super-resolution", "0.05", "2x, 100 steps", "4x, 500 steps"],
    ["Random inpainting", "0.01", "70% missing, 100 steps", "70% missing, 200 steps"],
    ["Box inpainting", "0.05", "40 x 40, 100 steps", "80 x 80, 100 steps"],
  ];
  const table = slide.tables.add({
    rows: values.length,
    columns: 4,
    left: 86,
    top: 150,
    width: 1108,
    height: 390,
    columnTracks: [{ mode: "fr", value: 1.35 }, { mode: "fr", value: 0.8 }, { mode: "fr", value: 1.8 }, { mode: "fr", value: 1.8 }],
    values,
  });
  table.styleOptions = { headerRow: true, bandedRows: true };
  table.borders.assign({ style: "solid", fill: C.grid, width: 1 });
  for (let column = 0; column < 4; column += 1) table.getCell(0, column).fill = C.navy;
  table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: 4 }).assign({
    textStyle: { typeface: family, fontSize: 17, bold: true, color: C.white },
    margins: { top: 10, right: 10, bottom: 10, left: 10 },
  });
  table.cells.block({ row: 1, column: 0, rowCount: 5, columnCount: 4 }).assign({
    textStyle: { typeface: family, fontSize: 16, color: C.ink },
    margins: { top: 9, right: 10, bottom: 9, left: 10 },
    anchor: "middle",
  });
  textBox(slide, "20 images x 5 ratios x 5 tasks x 2 datasets = 1,000 reconstructions", 126, 574, 1028, 52, { fontSize: 24, bold: true, color: C.blue, alignment: "center" });
  footer(slide);
  notes(slide, "All five task noise levels are nonzero, so the same ratio sweep is meaningful for every operator.", ["FLOWER paper Section 5.1: https://openreview.net/forum?id=QGd34p02mI", "Configuration: config/robustness.json"]);
}

function addDeltaChartSlide(dataset, slideNumber) {
  const slide = presentation.slides.add();
  header(slide, `${datasetLabels[dataset]} paired PSNR response`, slideNumber);
  const allValues = tasks.flatMap((task) => ratios.map((ratio) => Number(rowFor(dataset, task, ratio).psnr_delta_vs_correct_mean)));
  const bound = Math.max(1, Math.ceil(Math.max(...allValues.map(Math.abs))));
  const chart = styleChart(slide.charts.add("line", {
    position: { left: 70, top: 140, width: 820, height: 470 },
    categories: ratios.map((ratio) => `${ratio}`),
    series: tasks.map((task, index) => ({
      name: taskLabels[task],
      values: ratios.map((ratio) => Number(rowFor(dataset, task, ratio).psnr_delta_vs_correct_mean)),
      line: { style: "solid", fill: taskColors[index], width: 3 },
      marker: { symbol: "circle", size: 7 },
    })),
    hasLegend: true,
    legend: { position: "bottom", textStyle: { typeface: family, fontSize: 11, fill: C.muted } },
    xAxis: {
      title: { text: "Assumed sigma divided by true sigma", textStyle: { typeface: family, fontSize: 13, fill: C.muted } },
      textStyle: { typeface: family, fontSize: 12, fill: C.muted },
      majorGridlines: null,
    },
    yAxis: {
      title: { text: "Paired delta PSNR in dB", textStyle: { typeface: family, fontSize: 13, fill: C.muted } },
      min: -bound,
      max: bound,
      majorUnit: Math.max(0.5, Math.ceil(bound / 4)),
      numberFormatCode: "0.0",
      textStyle: { typeface: family, fontSize: 12, fill: C.muted },
      majorGridlines: { style: "solid", fill: C.grid, width: 1 },
    },
  }));
  const ordered = tasks.map((task) => ({ task, value: sensitivity(dataset, task) })).sort((a, b) => b.value - a.value);
  textBox(slide, "Most sensitive task", 930, 164, 260, 24, { fontSize: 15, bold: true, color: C.coral, alignment: "center" });
  textBox(slide, taskLabels[ordered[0].task], 930, 198, 260, 56, { fontSize: 25, bold: true, color: C.navy, alignment: "center" });
  textBox(slide, `${ordered[0].value.toFixed(2)} dB mean absolute response`, 930, 260, 260, 48, { fontSize: 17, color: C.muted, alignment: "center" });
  textBox(slide, "Least sensitive task", 930, 364, 260, 24, { fontSize: 15, bold: true, color: C.green, alignment: "center" });
  textBox(slide, taskLabels[ordered[ordered.length - 1].task], 930, 398, 260, 56, { fontSize: 25, bold: true, color: C.navy, alignment: "center" });
  textBox(slide, `${ordered[ordered.length - 1].value.toFixed(2)} dB mean absolute response`, 930, 460, 260, 48, { fontSize: 17, color: C.muted, alignment: "center" });
  footer(slide);
  notes(slide, "Each line uses the same 20 images and paired control. The report includes 95 percent confidence intervals and the full metric table.", ["Data: artifacts/experiments/main/summary.csv"]);
}

addDeltaChartSlide("celeba", 6);
addDeltaChartSlide("afhq_cat", 7);

// Slide 8
{
  const slide = presentation.slides.add();
  header(slide, "Control results and the paper reference", 8);
  addResultsTable(slide, "celeba", 72);
  addResultsTable(slide, "afhq_cat", 660);
  textBox(slide, "Our control uses 20 fixed images from each paper benchmark pool. The paper values average 100 images, so the differences are contextual rather than exact replication errors.", 132, 568, 1016, 62, { fontSize: 18, color: C.muted, alignment: "center" });
  footer(slide);
  notes(slide, "The ratio 1.0 control provides a sanity check against the published Flower1-OT scale. The image samples differ in size, so paired conclusions rely on within-project deltas.", ["FLOWER Tables 1 and 2: https://openreview.net/forum?id=QGd34p02mI", "Data: artifacts/experiments/main/summary.csv"]);
}

// Slide 9
{
  const slide = presentation.slides.add();
  header(slide, "CelebA final reconstructions", 9);
  await addImage(slide, "artifacts/figures/figure2_celeba_qualitative.png", { left: 58, top: 128, width: 1164, height: 470 }, "CelebA reconstructions for the most and least sensitive tasks");
  textBox(slide, "One image was selected before examining results. The two tasks follow the highest and lowest sensitivity rule.", 142, 612, 996, 42, { fontSize: 18, color: C.muted, alignment: "center" });
  footer(slide);
  notes(slide, "Read each row from the same ground truth and measurement through all five assumed noise ratios.", ["Generated figure: artifacts/figures/figure2_celeba_qualitative.png"]);
}

// Slide 10
{
  const slide = presentation.slides.add();
  header(slide, "AFHQ-Cat final reconstructions", 10);
  await addImage(slide, "artifacts/figures/figure3_afhq_qualitative.png", { left: 58, top: 128, width: 1164, height: 470 }, "AFHQ-Cat reconstructions for the most and least sensitive tasks");
  textBox(slide, "The same visual test checks whether the mismatch pattern extends beyond aligned human faces.", 142, 612, 996, 42, { fontSize: 18, color: C.muted, alignment: "center" });
  footer(slide);
  notes(slide, "The AFHQ-Cat row uses the same predeclared qualitative image position and task-selection rule as CelebA.", ["Generated figure: artifacts/figures/figure3_afhq_qualitative.png"]);
}

// Slide 11
{
  const slide = presentation.slides.add();
  header(slide, "Noise mismatch changes the reconstruction trajectory", 11);
  await addImage(slide, "artifacts/figures/figure4_trajectory.png", { left: 196, top: 118, width: 888, height: 526 }, "FLOWER trajectories for five noise ratios at five flow times");
  footer(slide);
  notes(slide, "The setting has the highest mean absolute paired PSNR response. Its displayed image is closest to median image-level sensitivity, which avoids selecting an extreme failure.", ["Selection metadata: artifacts/experiments/main/analysis_capture/metadata.json", "Generated figure: artifacts/figures/figure4_trajectory.png"]);
}

// Slide 12
{
  const slide = presentation.slides.add();
  header(slide, "The direct effect appears in measurement refinement", 12);
  await addImage(slide, "artifacts/figures/figure5_internal_states.png", { left: 52, top: 150, width: 1176, height: 442 }, "FLOWER prior destination, measurement refinement, and next state");
  textBox(slide, "Columns compare the prior destination, refined destination, and next trajectory state at three times. Rows compare ratios 0.5, 1.0, and 1.5.", 118, 608, 1044, 50, { fontSize: 17, color: C.muted, alignment: "center" });
  footer(slide);
  notes(slide, "Sigma enters Step 2 directly. Step 1 has no explicit sigma term, although its input state can already differ because of earlier refinements.", ["Generated figure: artifacts/figures/figure5_internal_states.png", "FLOWER paper Figure 3 and Proposition 2: https://openreview.net/forum?id=QGd34p02mI"]);
}

// Slide 13
{
  const slide = presentation.slides.add();
  header(slide, "Sensitivity depends strongly on the inverse problem", 13);
  const topSettings = rankedSettings.slice(0, 6).reverse();
  const chart = styleChart(slide.charts.add("bar", {
    position: { left: 66, top: 146, width: 650, height: 450 },
    categories: topSettings.map((item) => `${datasetLabels[item.dataset]} ${taskLabels[item.task]}`),
    series: [{ name: "Mean absolute paired PSNR response", values: topSettings.map((item) => item.value), fill: C.blue }],
    barOptions: { direction: "bar", grouping: "clustered" },
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd", numberFormatCode: "0.00" },
    xAxis: { title: { text: "Mean absolute delta PSNR in dB", textStyle: { typeface: family, fontSize: 13, fill: C.muted } }, textStyle: { typeface: family, fontSize: 11, fill: C.muted }, majorGridlines: { style: "solid", fill: C.grid, width: 1 } },
    yAxis: { textStyle: { typeface: family, fontSize: 11, fill: C.muted }, majorGridlines: null },
  }));
  textBox(slide, "Highest response", 780, 154, 390, 28, { fontSize: 16, bold: true, color: C.coral });
  textBox(slide, `${datasetLabels[mostSensitive.dataset]} ${taskLabels[mostSensitive.task]}`, 780, 190, 390, 54, { fontSize: 27, bold: true, color: C.navy });
  textBox(slide, `${mostSensitive.value.toFixed(2)} dB mean absolute paired change`, 780, 248, 390, 40, { fontSize: 18, color: C.muted });
  textBox(slide, "Main conclusion", 780, 340, 390, 28, { fontSize: 16, bold: true, color: C.green });
  textBox(slide, "Noise calibration matters most where the response curve is steep. Flat curves indicate tolerance within the tested range.", 780, 378, 390, 118, { fontSize: 22, bold: true, color: C.navy });
  textBox(slide, "Evidence boundary", 780, 534, 390, 24, { fontSize: 15, bold: true, color: C.purple });
  textBox(slide, "The claims apply to the released Flower1-OT models, five tested ratios, and fixed 20-image samples.", 780, 566, 390, 70, { fontSize: 17, color: C.muted });
  footer(slide, "Full tables, confidence intervals, mathematical derivations, and limitations are in the report");
  notes(slide, "The ranking averages the absolute paired PSNR response across the four mismatched ratios. The report also discusses directionality, uncertainty, and limitations.", ["Data: artifacts/experiments/main/summary.csv", "Report: artifacts/report/flower-noise-scale-mismatch-report.docx"]);
}

const candidatePath = path.join(BUILD_DIR, "candidate-v1.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const requirements = {
  explicitTotalSlideCount: 13,
  requiredNativeTableOwnerSlides: [5, 8],
  requiredNativeChartOwnerSlides: [6, 7, 13],
  materializeLiteralChartWorkbooks: true,
};
const fontPolicy = { basis: "design", families: [family] };
const result = await finalizePresentation({
  ...requirements,
  workspaceDir: ROOT,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
    "--require-native-table-slide", "5",
    "--require-native-table-slide", "8",
  ],
  requiredNativeTableOwnerSlides: requirements.requiredNativeTableOwnerSlides,
  requiredNativeChartOwnerSlides: requirements.requiredNativeChartOwnerSlides,
  materializeLiteralChartWorkbooks: true,
  fontPolicy,
  verifyArtifactToolImport: true,
  receiptPath: path.join(STAGING_DIR, "flower-noise-scale-mismatch-v1.validation.json"),
});

console.log(JSON.stringify({ family, final: FINAL_PPTX, result }, null, 2));
