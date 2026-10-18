#!/usr/bin/env python3
"""Validate the final deliverables and package their current sources and results."""
from collections import defaultdict
from pathlib import Path
import csv
import hashlib
import json
import math
import re
import statistics
import zipfile
from lxml import etree as E
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'artifacts/experiments/main'
REPORT = ROOT / 'artifacts/report/FLOWER_Noise_Mismatch_Report.pdf'
TEX = REPORT.with_suffix('.tex')
PPTX = ROOT / 'artifacts/presentation/FLOWER_Noise_Mismatch_Presentation.pptx'
SLIDES = PPTX.with_suffix('.pdf')
DESTINATION = ROOT / 'artifacts/delivery/FLOWER_Noise_Mismatch_Project.zip'
NS = {'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def csv_rows(name):
    with (DATA / name).open() as stream:
        return list(csv.DictReader(stream))


def main():
    rows, summary = csv_rows('metrics.csv'), csv_rows('summary.csv')
    assert len(rows) == 1000 and len(summary) == 50
    keys = [(r['dataset'], r['task'], r['image'], float(r['assumed_to_true_sigma'])) for r in rows]
    assert len(set(keys)) == 1000
    controls = {k[:3]: r for k, r in zip(keys, rows) if k[3] == 1}
    groups = defaultdict(list)
    for key, row in zip(keys, rows):
        groups[key[0], key[1], key[3]].append(row)
        assert all(math.isfinite(float(row[m])) for m in ['psnr', 'ssim', 'lpips'])
        assert math.isclose(float(row['assumed_to_true_variance']), key[3] ** 2)
        for field in ['measurement_seed', 'solver_seed', 'image_position', 'paper_index', 'steps', 'true_sigma']:
            assert row[field] == controls[key[:3]][field]
    for aggregate in summary:
        group = groups[aggregate['dataset'], aggregate['task'], float(aggregate['assumed_to_true_sigma'])]
        assert len(group) == int(aggregate['n']) == 20
        for metric in ['psnr', 'ssim', 'lpips']:
            values = [float(row[metric]) for row in group]
            changes = [float(row[metric]) - float(controls[row['dataset'], row['task'], row['image']][metric]) for row in group]
            for suffix, observations in [('', values), ('_delta_vs_correct', changes)]:
                assert math.isclose(statistics.mean(observations), float(aggregate[metric + suffix + '_mean']), abs_tol=1e-10)
                assert math.isclose(1.96 * statistics.stdev(observations) / math.sqrt(20),
                                    float(aggregate[metric + suffix + '_ci95']), abs_tol=1e-10)
    provenance = json.loads((ROOT / 'artifacts/figures/publication/provenance.json').read_text())
    for name, expected in provenance['source_csv_sha256'].items():
        assert digest(DATA / name) == expected, f'Experimental data changed: {name}'

    report = PdfReader(REPORT)
    assert len(report.pages) == 25 and len(PdfReader(SLIDES).pages) == 20
    report_text = '\n'.join(page.extract_text() for page in report.pages)
    assert 'normalize=True' in report.pages[7].extract_text()
    assert report_text.count('qualitative comparison (continued)') == 2
    assert 'Figure 15:' in report_text
    assert {p.name for p in REPORT.parent.iterdir() if not p.name.startswith('.')} == {REPORT.name, TEX.name}
    assert {p.name for p in PPTX.parent.iterdir() if not p.name.startswith('.')} == {PPTX.name, SLIDES.name}
    figures = ROOT / 'artifacts/figures/publication'
    assert len(list(figures.glob('*.png'))) == 15
    assert len(list((figures / 'details').glob('*.pdf'))) == 2

    with zipfile.ZipFile(PPTX) as archive:
        assert archive.testzip() is None
        assert len([n for n in archive.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)]) == 20
        charts = [n for n in archive.namelist() if re.fullmatch(r'ppt/(?:slides/)?charts/chart\d+\.xml', n)]
        assert len(charts) == 6
        assert len([n for n in archive.namelist() if n.endswith('.xlsx')]) == 6
        for name in charts:
            chart = E.fromstring(archive.read(name))
            assert len(chart.findall('.//c:errBars', NS)) == 5
        crop_count = 0
        for number in range(11, 16):
            tree = E.fromstring(archive.read(f'ppt/slides/slide{number}.xml'))
            assert len(tree.findall('.//p:pic', NS)) == 28
            for crop in tree.findall('.//p:pic/p:blipFill/a:srcRect', NS):
                if int(crop.get('l', '0')) > 0:
                    assert sum(int(crop.get(k, '0')) for k in ['l', 'r']) == 54000
                    assert sum(int(crop.get(k, '0')) for k in ['t', 'b']) == 54000
                    crop_count += 1
        assert crop_count == 70

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'report_pages': 25, 'presentation_slides': 20,
                'verified_reconstructions': 1000, 'summary_groups': 50,
                'publication_figures': 15, 'report_detail_panels': 2,
                'presentation_detail_crops': crop_count,
                'files': {str(p.relative_to(ROOT)): digest(p) for p in [REPORT, TEX, PPTX, SLIDES]},
                'source_csv_sha256': provenance['source_csv_sha256']}
    manifest_path = DESTINATION.parent / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')

    # Check local documentation links against the new canonical filenames.
    for document in [ROOT / 'README.md', ROOT / 'artifacts/README.md']:
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', document.read_text()):
            if '://' not in target and not target.startswith('#'):
                assert (document.parent / target.split('#')[0]).exists(), (document, target)

    files = set()
    for folder in ['artifacts/experiments/main', 'artifacts/figures/publication',
                   'config', 'data_splits', 'experiments', 'robust_flower', 'scripts',
                   'notebooks', 'tests', 'pnpflow', 'tools']:
        for file in (ROOT / folder).rglob('*'):
            if file.is_file() and file.name != '.DS_Store' and '__pycache__' not in file.parts and file.suffix != '.pyc':
                files.add(file)
    files.update([REPORT, TEX, PPTX, SLIDES, manifest_path])
    for name in ['README.md', 'artifacts/README.md', 'artifacts/problem_statement.md',
                 'requirements-robustness.txt', 'requirements-deliverables.txt', 'LICENSE', 'Flower_main.pdf']:
        file = ROOT / name
        if file.exists():
            files.add(file)
    with zipfile.ZipFile(DESTINATION, 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(files):
            archive.write(file, file.relative_to(ROOT))
    with zipfile.ZipFile(DESTINATION) as archive:
        assert archive.testzip() is None
    print(json.dumps({**manifest, 'packaged_files': len(files),
                      'package': str(DESTINATION), 'package_bytes': DESTINATION.stat().st_size}, indent=2))


if __name__ == '__main__':
    main()
