#!/usr/bin/env python3
"""Selected report detail panels from saved reconstructions, without inference.

Each row uses one fixed, recorded crop for its ground truth and all noise ratios.
The existing overview figures and all measured metrics remain unchanged.
"""
from pathlib import Path
import csv
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'artifacts/build/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image
import numpy as np

RESULTS = ROOT / 'artifacts/experiments/main'
OUT = ROOT / 'artifacts/figures/publication/details'
BUILD = ROOT / 'artifacts/build/report-detail-update'
RATIOS = [0.5, 0.75, 1, 1.25, 1.5]
TASKS = [('denoising', 'Denoising'), ('super_resolution', 'Super-\nresolution')]
DATASETS = {
    'celeba': {'name': 'CelebA', 'image': '182702.jpg', 'bounds': [.24, .31, .70, .77]},
    'afhq_cat': {'name': 'AFHQ-Cat', 'image': 'pixabay_cat_001348.jpg', 'bounds': [.26, .29, .72, .75]},
}
BLUE = '#3155A4'
GRAY = '#56616D'


def show(ax, filename, bounds=None, correct=False):
    with Image.open(filename) as image:
        pixels = np.asarray(image)
    height, width = pixels.shape[:2]
    ax.imshow(pixels, interpolation='nearest')
    if bounds is not None:
        left, top, right, bottom = bounds
        ax.set_xlim(left * width - .5, right * width - .5)
        ax.set_ylim(bottom * height - .5, top * height - .5)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor(BLUE if correct else '#CCD2D9')
        spine.set_linewidth(2 if correct else .7)
    return width, height


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'text.color': '#20252C', 'figure.facecolor': 'white',
                         'savefig.facecolor': 'white'})
    with (RESULTS / 'metrics.csv').open() as stream:
        metrics = list(csv.DictReader(stream))
    provenance = {'generator': 'tools/build_report_detail_crops.py',
                  'inference_performed': False,
                  'metric_scope': 'full image, not cropped region',
                  'metrics_sha256': hashlib.sha256((RESULTS / 'metrics.csv').read_bytes()).hexdigest(),
                  'panels': []}
    for dataset, info in DATASETS.items():
        fig, axes = plt.subplots(2, 7, figsize=(12.6, 5.6))
        fig.subplots_adjust(left=.115, right=.99, top=.73, bottom=.16,
                            wspace=.12, hspace=.40)
        fig.suptitle(f"{info['name']}: magnified reconstruction details",
                     y=.985, fontsize=17, fontweight='bold')
        fig.text(.55, .91, f"Fixed example: {info['image']}. Identical crop across all five assumed noise levels.",
                 ha='center', fontsize=10.5, color=GRAY)
        titles = ['Crop location', 'Ground-truth\ncrop'] + [
            f'r = {r:.2f}' + ('\n(correct)' if r == 1 else '') for r in RATIOS]
        for row, (task, label) in enumerate(TASKS):
            directories = sorted((RESULTS / 'reconstructions' / dataset / task).glob('image_*'))
            if len(directories) != 1:
                raise ValueError(f'Ambiguous saved example: {directories}')
            directory = directories[0]
            ground_truth = directory / 'ground_truth.png'
            width, height = show(axes[row, 0], ground_truth)
            left, top, right, bottom = info['bounds']
            axes[row, 0].add_patch(Rectangle((left * width - .5, top * height - .5),
                (right - left) * width, (bottom - top) * height,
                linewidth=1.4, edgecolor='#E5A52D', facecolor='none'))
            axes[row, 0].text(-.13, .5, label, transform=axes[row, 0].transAxes,
                ha='right', va='center', fontsize=11, fontweight='bold')
            show(axes[row, 1], ground_truth, info['bounds'])
            for column, ratio in enumerate(RATIOS, 2):
                filename = directory / f'sigma_ratio_{ratio:g}.png'
                show(axes[row, column], filename, info['bounds'], correct=ratio == 1)
                selected = [r for r in metrics if r['dataset'] == dataset and r['task'] == task
                            and r['image'] == info['image']
                            and float(r['assumed_to_true_sigma']) == ratio]
                if len(selected) != 1:
                    raise ValueError(f'Missing unique image metric: {dataset}, {task}, {ratio}')
                axes[row, column].set_xlabel(f"{float(selected[0]['psnr']):.2f} dB",
                                             fontsize=10.5, labelpad=5)
            for column, title in enumerate(titles):
                if row == 0:
                    axes[row, column].set_title(title, fontsize=10.5, pad=10,
                        fontweight='bold' if column == 4 else 'normal')
            provenance['panels'].append({'dataset': dataset, 'task': task,
                'image': info['image'], 'normalized_bounds': info['bounds'],
                'ground_truth_sha256': hashlib.sha256(ground_truth.read_bytes()).hexdigest(),
                'source_directory': str(directory.relative_to(ROOT))})
        fig.text(.55, .052,
                 'Gold box: crop location. All detail panels use the same region. Blue frame: correct-noise control (r = 1).\n'
                 'Numbers are full-image PSNR in dB, not crop-specific scores. The original measurements and reconstructions are unchanged.',
                 ha='center', va='center', fontsize=9, color=GRAY, linespacing=1.55)
        name = f'{"05" if dataset == "celeba" else "06"}_{dataset}_detail_crops'
        fig.savefig(OUT / f'{name}.png', dpi=300, bbox_inches='tight', pad_inches=.15)
        fig.savefig(OUT / f'{name}.pdf', bbox_inches='tight', pad_inches=.15)
        plt.close(fig)
    (BUILD / 'crop-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print('Created two selected detail panels from existing experiment images.')


if __name__ == '__main__':
    main()
