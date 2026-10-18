/** Apply the final narrative and matched detail layout to a freshly built deck. */
import fs from 'node:fs/promises';
import path from 'node:path';

export async function applyFinalPresentationContent(p, { root: ROOT, buildDir: BUILD, font: FONT }) {
const BLUE = '#303EAD', INK = '#222222', GRAY = '#5B616A';
await fs.mkdir(BUILD, { recursive: true });
const before = await p.inspect({ kind: 'slide,textbox,shape,image,table,chart,notes,layout', maxChars: 500000 });
await fs.writeFile(path.join(BUILD, 'before.ndjson'), before.ndjson);
const records = before.ndjson.trim().split('\n').map(line => JSON.parse(line));

function record(slideNumber, predicate) {
  const hits = records.filter(r => r.slide === slideNumber && predicate(r));
  if (hits.length !== 1) throw new Error(`Expected one object on slide ${slideNumber}, got ${hits.length}`);
  return hits[0];
}
function slide(n) { return p.resolve(record(n, r => r.kind === 'slide').id); }
function byText(n, value) {
  return p.resolve(record(n, r => r.kind === 'textbox' && r.text === value).id);
}
function byPrefix(n, value) {
  return p.resolve(record(n, r => r.kind === 'textbox' && r.text?.startsWith(value)).id);
}
function byBox(n, box) {
  return p.resolve(record(n, r => r.kind === 'shape' && r.bbox?.every((v, i) => Math.abs(v - box[i]) < 0.1)).id);
}
function position(object, x, y, w, h) { object.position = { left: x, top: y, width: w, height: h }; }
function style(object, size, color = INK, bold = false, alignment = 'left') {
  object.text.style = { typeface: FONT, fontSize: size, color, bold, alignment,
    verticalAlignment: 'middle', autoFit: 'none', wrap: true };
}
function text(s, value, x, y, w, h, size = 24, color = INK, bold = false, alignment = 'left') {
  const o = s.shapes.add({ geometry: 'textbox', position: { left: x, top: y, width: w, height: h },
    fill: 'none', line: { fill: 'none', width: 0 } });
  o.text = value; style(o, size, color, bold, alignment); return o;
}
function outline(s, x, y, w, h, color, width = 1.4) {
  return s.shapes.add({ geometry: 'rect', position: { left: x, top: y, width: w, height: h },
    fill: 'none', line: { fill: color, style: 'solid', width } });
}
function appendNote(n, value) {
  const previous = record(n, r => r.kind === 'notes').text;
  slide(n).speakerNotes.textFrame.setText(`${previous}\n\n${value}`);
}

// State exactly what was manipulated, while retaining the paired design.
byText(4, 'The image, measurement and source-noise draws are shared across all five ratios. We compare every result with its r = 1 control.').text =
  'Same image, measurement and source-noise draws for every ratio. True σ and noise structure stay fixed. Only assumed σ changes.';
text(slide(4), 'r = 1 is the correct-noise control', 100, 353, 800, 28, 21, GRAY, false, 'center');

const design = slide(5);
position(byText(5, '20 fixed CelebA images + 20 fixed AFHQ-Cat images'), 44, 99, 912, 42);
text(design, 'Only assumed σ changes. Fixed image, H, measurement and noise structure. γ = 0.',
  44, 147, 912, 28, 21, BLUE, false, 'center');
position(byText(5, 'PSNR ↑      SSIM ↑      LPIPS ↓'), 44, 598, 912, 37);
text(design, 'ΔM(r) = M(r) − M(1)', 44, 641, 912, 34, 29, BLUE, true, 'center');
text(design, 'Zero = no change. PSNR / SSIM: positive is better. LPIPS: negative is better.',
  44, 678, 912, 26, 21, INK, false, 'center');
appendNote(5, 'The Gaussian noise covariance is σ_true² I, with the same spatial structure for every assumed ratio. Gamma is zero in every completed run. For each metric M, the plot shows the mean of paired differences M_i(r) − M_i(1). Zero denotes no change relative to the matched-noise control, not zero absolute quality.');

for (const n of [6, 7]) {
  const c = p.resolve(record(n, r => r.kind === 'chart').id);
  c.title = 'Change from the correct-noise control (r = 1)';
  byPrefix(n, 'Mean paired ΔPSNR vs r = 1.').text =
    'ΔPSNR = PSNR(r) − PSNR(1). Zero = no change. Higher is better. n = 20. Error bars: approximate 95% CI.';
}

// Preserve every full image, all five ratios, and the numerical labels.
// Crops are native image crops of the saved experiment files, never generated imagery.
const tasks = ['denoising', 'gaussian_deblurring', 'super_resolution', 'random_inpainting', 'box_inpainting'];
const datasets = ['celeba', 'afhq_cat'];
const datasetNames = { celeba: 'CelebA', afhq_cat: 'AFHQ-Cat' };
const ratios = [0.5, 0.75, 1, 1.25, 1.5];
const columns = ['Ground truth', 'Measurement', ...ratios.map(r => `r = ${r.toFixed(2)}`)];
const files = ['ground_truth.png', 'measurement.png', ...ratios.map(r => `sigma_ratio_${r}.png`)];
const visualMessages = [
  'Lower assumed noise leaves more fine-scale variation. Higher assumed noise smooths it.',
  'The two domains respond differently. Blur kernels and image content also differ.',
  'At r = 0.50, both datasets improve in all three metrics on average across 20 images.',
  'Changes are small across this range. This task also has the lowest true σ, 0.01.',
  'The central region is unobserved. The prior and observed pixels jointly guide its reconstruction.'
];
const cropProvenance = [];
for (let k = 0; k < tasks.length; k++) {
  const n = 11 + k, s = slide(n), task = tasks[k];
  for (let j = 0; j < columns.length; j++) position(byText(n, columns[j]), 45 + j * 132, 91, 126, 30);
  for (const [di, d] of datasets.entries()) {
    const originalY = 177 + di * 213;
    const rowY = 146 + di * 277;
    const cropY = rowY + 88;
    const imageBase = path.join(ROOT, 'artifacts/experiments/main/reconstructions', d, task);
    const imageDirs = (await fs.readdir(imageBase)).filter(name => name.startsWith('image_'));
    if (imageDirs.length !== 1) throw new Error(`Ambiguous saved example: ${imageBase}`);
    const imageDir = path.join(imageBase, imageDirs[0]);
    // Both crops include eyes and nearby texture. Box inpainting centers on the missing region.
    const roi = task === 'box_inpainting' ? [0.27, 0.27, 0.73, 0.73]
      : d === 'celeba' ? [0.24, 0.31, 0.70, 0.77] : [0.26, 0.29, 0.72, 0.75];
    const [left, top, right, bottom] = roi;
    const crop = { left, top, right: 1 - right, bottom: 1 - bottom };
    const label = byText(n, datasetNames[d]);
    label.text = `${datasetNames[d]}: full image above, 3× detail below`;
    position(label, 45, rowY - 28, 912, 26); style(label, 23, BLUE, true);
    const border = byBox(n, [43 + 4 * 132, originalY - 2, 130, 130]);
    position(border, 45 + 4 * 132 + 22, rowY - 2, 82, 82);
    for (let j = 0; j < columns.length; j++) {
      const x = 45 + j * 132;
      const oldImage = p.resolve(record(n, r => r.kind === 'image' && r.bbox &&
        Math.abs(r.bbox[0] - x) < 0.1 && Math.abs(r.bbox[1] - originalY) < 0.1).id);
      oldImage.frame = { left: x + 24, top: rowY, width: 78, height: 78 };
      // The region box is an editable scientific annotation, with identical coordinates across the row.
      outline(s, x + 24 + left * 78, rowY + top * 78, (right - left) * 78, (bottom - top) * 78, '#E9A93D', 1.1);
      const zoom = s.images.add({ blob: await fs.readFile(path.join(imageDir, files[j])), contentType: 'image/png',
        alt: `${datasetNames[d]} ${task} ${columns[j]} magnified matched crop`,
        position: { left: x + 8, top: cropY, width: 110, height: 110 }, crop, fit: 'cover' });
      zoom.crop = crop;
      outline(s, x + 6, cropY - 2, 114, 114, j === 4 ? BLUE : '#D5D8DF', j === 4 ? 2 : 0.8);
      if (j >= 2) {
        const metricRecord = record(n, r => r.kind === 'textbox' && r.bbox &&
          Math.abs(r.bbox[0] - x) < 0.1 && Math.abs(r.bbox[1] - (originalY + 132)) < 0.1);
        const metric = p.resolve(metricRecord.id);
        position(metric, x, cropY + 115, 126, 39); style(metric, 18, INK, false, 'center');
      }
    }
    cropProvenance.push({ slide: n, dataset: d, task, imageDirectory: path.relative(ROOT, imageDir),
      normalizedBounds: roi, displayMagnification: 110 / (78 * (right - left)) });
  }
  const background = byBox(n, [44, 586, 912, 109]);
  position(background, 44, 679, 912, 32); background.shadow = 'shadow-none';
  position(byBox(n, [44, 586, 912, 40]), 44, 679, 106, 32);
  const observation = byText(n, 'Observation');
  observation.text = 'Finding';
  position(observation, 51, 681, 96, 28); style(observation, 19, '#FFFFFF');
  const body = byPrefix(n, ['Underestimation preserves', 'The two datasets respond', 'Both datasets gain', 'The reconstruction changes', 'The data term acts'][k]);
  body.text = visualMessages[k]; position(body, 159, 681, 787, 28); style(body, 19);
  const footer = byPrefix(n, 'Numbers: PSNR (dB)');
  footer.text = 'Metrics: full-image PSNR (dB) / SSIM, then LPIPS. Gold box: crop region. Blue frame: r = 1. Measurement: Hᵀy.';
  position(footer, 40, 716, 920, 25); style(footer, 14, GRAY);
  appendNote(n, 'Full images and identically located crops are both displayed for the saved example. Gold boxes mark the crop on the full image. The effective detail magnification is approximately 3× relative to the full-image display. Metrics are unchanged and refer to the entire image, not the cropped region. Crop coordinates are stored in the revision provenance.');
}

// Separate plausible mechanisms from findings that the completed experiment establishes.
byText(18, 'Why the Forward Operator Matters').text = 'Possible Explanation: Measurement Constraints';
byPrefix(18, 'Denoising changes the measurement weight').text =
  'Denoising constrains every pixel. Masking and subsampling constrain observed locations directly. True noise levels also differ across tasks.';
byText(18, 'Why Correct Noise Need Not Maximize PSNR').text = 'Possible Explanation: Approximation Error';
byPrefix(18, 'The practical solver uses a learned velocity').text =
  'A different measurement weight may partly compensate for prior or solver approximation errors. The experiment does not establish why underestimation sometimes improves the metrics.';
byPrefix(18, '20 images per dataset and one paired seed').text =
  '20 images per dataset versus 100 in the paper. One paired seed sequence per image and task. Task and true noise level vary together.';
byPrefix(18, 'These results establish sensitivity').text =
  'These explanations are hypotheses. The measured effects apply to the tested sample, tasks and noise ratios.';
appendNote(18, 'The experiment demonstrates empirical sensitivity but does not isolate its mechanism. In particular, it does not prove that endpoint-approximation error causes the super-resolution gains. Operator type, true noise level and degradation severity are not independently varied.');

// Answer the research question before giving the supporting conclusions.
text(slide(19), 'FLOWER shows task-dependent robustness\nto an incorrect assumed noise level',
  44, 96, 912, 72, 31, BLUE, true, 'center');
for (const [oldY, oldH, newY, newH, header, prefix, bodyText] of [
  [124, 139, 186, 126, 'Sensitivity Depends on the Task', 'Denoising is the most sensitive setting.',
    'Denoising has the largest PSNR losses. Random inpainting changes very little in the tested settings.'],
  [292, 138, 334, 126, 'Overestimation Consistently Hurts Mean PSNR', 'Both r = 1.25 and r = 1.50 reduce',
    'Both r = 1.25 and r = 1.50 reduce mean PSNR in all ten tested dataset–task settings.'],
  [459, 171, 482, 151, 'Underestimation Has No Universal Outcome', 'Super-resolution improves in both datasets.',
    'Underestimation improves super-resolution here, but strong underestimation hurts denoising. LPIPS can disagree with PSNR and SSIM.']
]) {
  position(byBox(19, [44, oldY, 912, oldH]), 44, newY, 912, newH);
  position(byBox(19, [44, oldY, 912, 40]), 44, newY, 912, 40);
  const heading = byText(19, header); position(heading, 57, newY + 3, 886, 33); style(heading, 27, '#FFFFFF');
  const body = byPrefix(19, prefix); body.text = bodyText;
  position(body, 59, newY + 49, 882, newH - 60); style(body, 27);
}
const concludingLine = byText(19, 'Noise calibration should be evaluated for the task and the metric.');
concludingLine.text = 'Conclusions apply to the tested images, settings and noise ratios.';
position(concludingLine, 44, 662, 912, 42); style(concludingLine, 26, BLUE, true, 'center');

const after = await p.inspect({ kind: 'slide,textbox,shape,image,table,chart,notes,layout', maxChars: 600000 });
await fs.writeFile(path.join(BUILD, 'after.ndjson'), after.ndjson);
return cropProvenance;
}
