#!/usr/bin/env python3
"""Verify the completed results and package the current deliverables; no inference."""
from pathlib import Path
import csv, hashlib, json, math, re, statistics, subprocess, zipfile
from collections import defaultdict
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'artifacts/experiments/main'
def csv_rows(name):
    with (DATA/name).open() as f:return list(csv.DictReader(f))
rows=csv_rows('metrics.csv'); summary=csv_rows('summary.csv')
assert len(rows)==1000 and len(summary)==50
keys=[(r['dataset'],r['task'],r['image'],float(r['assumed_to_true_sigma'])) for r in rows]
assert len(set(keys))==1000
groups=defaultdict(list)
controls={key[:3]:r for key,r in zip(keys,rows) if key[3]==1}
for key,r in zip(keys,rows):
    groups[key[0],key[1],key[3]].append(r)
    for metric in ['psnr','ssim','lpips']:assert math.isfinite(float(r[metric]))
    assert math.isclose(float(r['assumed_to_true_variance']),key[3]**2)
    control=controls[key[:3]]
    for field in ['measurement_seed','solver_seed','image_position','paper_index','steps','true_sigma']:
        assert r[field]==control[field],(key,field)
for s in summary:
    group=groups[s['dataset'],s['task'],float(s['assumed_to_true_sigma'])]
    assert len(group)==int(s['n'])==20
    for metric in ['psnr','ssim','lpips']:
        vals=[float(r[metric]) for r in group]
        delta=[float(r[metric])-float(controls[r['dataset'],r['task'],r['image']][metric]) for r in group]
        for suffix,values in [('',vals),('_delta_vs_correct',delta)]:
            assert math.isclose(statistics.mean(values),float(s[metric+suffix+'_mean']),abs_tol=1e-10)
            assert math.isclose(1.96*statistics.stdev(values)/math.sqrt(20),float(s[metric+suffix+'_ci95']),abs_tol=1e-10)
provenance=json.loads((ROOT/'artifacts/figures/publication/provenance.json').read_text())
for name,digest in provenance['source_csv_sha256'].items():
    content=(DATA/name).read_bytes()
    assert hashlib.sha256(content).hexdigest()==digest
    original=subprocess.check_output(['git','show',f'HEAD:artifacts/experiments/main/{name}'],cwd=ROOT)
    assert content==original,f'Experimental data changed: {name}'
report=ROOT/'artifacts/report/robust-flower-report.pdf'
slides=ROOT/'artifacts/presentation/robust-flower-results.pdf'
pptx=ROOT/'artifacts/presentation/robust-flower-results.pptx'
assert len(PdfReader(report).pages)==21
assert len(PdfReader(slides).pages)==20
assert len(list((ROOT/'artifacts/figures/publication').glob('*.png')))==15
with zipfile.ZipFile(pptx) as z:
    assert z.testzip() is None
    assert len([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)])==20
    charts=[n for n in z.namelist() if re.fullmatch(r'ppt/(?:slides/)?charts/chart\d+\.xml',n)]
    assert len(charts)==6
    assert all(z.read(n).count(b'<c:errBars>')==5 for n in charts)

files=set()
for directory in ['artifacts/experiments/main','artifacts/figures/publication','config','data_splits','artifacts/build/redesign/figure-pdf']:
    files.update(p for p in (ROOT/directory).rglob('*') if p.is_file() and p.name!='.DS_Store')
for name in ['README.md','artifacts/README.md','artifacts/problem_statement.md',
             'artifacts/report/robust-flower-report.pdf','artifacts/report/robust-flower-report.tex',
             'artifacts/presentation/robust-flower-results.pptx','artifacts/presentation/robust-flower-results.pdf',
             'tools/redesign_figures.py','tools/build_academic_report.py','tools/report_template.tex',
             'tools/redesign_presentation.mjs','tools/patch_chart_confidence.py','tools/validate_and_package_deliverables.py']:
    files.add(ROOT/name)
destination=ROOT/'artifacts/delivery/Robust_FLOWER_Project.zip'
destination.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
    for file in sorted(files):z.write(file,file.relative_to(ROOT))
with zipfile.ZipFile(destination) as z:assert z.testzip() is None
print(json.dumps({'verified_rows':len(rows),'summary_groups':len(summary),'source_data_unchanged':True,
                  'report_pages':21,'presentation_slides':20,'figures':15,'packaged_files':len(files),
                  'package':str(destination),'package_bytes':destination.stat().st_size},indent=2))
