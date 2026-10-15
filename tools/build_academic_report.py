#!/usr/bin/env python3
"""Build the reference-styled LaTeX report using completed experimental data."""
from pathlib import Path
import csv
import json
import subprocess
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/report'
BUILD=ROOT/'artifacts/build/redesign/report'
TASKS=['denoising','gaussian_deblurring','super_resolution','random_inpainting','box_inpainting']
LABELS=['Denoising','Deblurring','Super-resolution','Random inpainting','Box inpainting']
NAMES={'celeba':'CelebA','afhq_cat':'AFHQ-Cat'}
with (ROOT/'artifacts/experiments/main/summary.csv').open() as f:
    rows=list(csv.DictReader(f))
BY={(r['dataset'],r['task'],float(r['assumed_to_true_sigma'])):r for r in rows}
CONFIG=json.loads((ROOT/'config/robustness.json').read_text())

def control_table():
    lines=[r'\begin{table}[H]\centering\small',
        r'\caption{Correct-noise control ($r=1$) and the published Flower1-OT reference. Our metric means use 20 images; paper PSNR uses 100 images. The last column is an absolute benchmark gap, not a mismatch effect.}',
        r'\label{tab:control}',r'\begin{tabular}{llrrrrr}',r'\toprule',
        r'Dataset & Task & PSNR & SSIM & LPIPS & Paper PSNR & Gap (dB)\\',r'\midrule']
    for d in NAMES:
        for i,(t,label) in enumerate(zip(TASKS,LABELS)):
            r=BY[d,t,1];p=float(CONFIG['paper_flower1_ot_reference'][d][t][0]);ps=float(r['psnr_mean'])
            lines.append(f"{NAMES[d] if i==0 else ''} & {label} & {ps:.2f} & {float(r['ssim_mean']):.3f} & {float(r['lpips_mean']):.3f} & {p:.2f} & {ps-p:+.2f} "+r'\\')
        if d=='celeba':lines.append(r'\midrule')
    lines.extend([r'\bottomrule',r'\end{tabular}',r'\end{table}'])
    return '\n'.join(lines)

def highlights():
    settings=[('celeba','denoising',.5),('afhq_cat','denoising',.5),('afhq_cat','denoising',.75),('celeba','super_resolution',.5),('afhq_cat','super_resolution',.5),('celeba','random_inpainting',1.5),('afhq_cat','random_inpainting',1.5)]
    lines=[r'\begin{table}[H]\centering\small',r'\caption{Selected paired changes that distinguish degradation, improvement, and metric disagreement. PSNR/SSIM improve upward; LPIPS improves downward. All entries are means over 20 images.}',r'\label{tab:highlights}',r'\begin{tabular}{llrrrr}',r'\toprule',r'Dataset & Task & $r$ & $\Delta$PSNR (dB) & $\Delta$SSIM & $\Delta$LPIPS\\',r'\midrule']
    for d,t,ratio in settings:
        r=BY[d,t,ratio]
        lines.append(f"{NAMES[d]} & {LABELS[TASKS.index(t)]} & {ratio:.2f} & {float(r['psnr_delta_vs_correct_mean']):+.3f} & {float(r['ssim_delta_vs_correct_mean']):+.4f} & {float(r['lpips_delta_vs_correct_mean']):+.4f}"+r'\\')
    lines.extend([r'\bottomrule',r'\end{tabular}',r'\end{table}']);return '\n'.join(lines)

def full_tables():
    parts=[]
    for d in NAMES:
        lines=[r'\begin{table}[p]\centering\small',f'\\caption{{Complete {NAMES[d]} results. Mean metrics over 20 fixed images per row.}}',f'\\label{{tab:full-{d}}}',r'\begin{tabular}{llrrrr}',r'\toprule',r'Task & $r$ & PSNR (dB) & SSIM & LPIPS & $\Delta$PSNR (dB)\\',r'\midrule']
        for i,(t,label) in enumerate(zip(TASKS,LABELS)):
            for j,ratio in enumerate([.5,.75,1,1.25,1.5]):
                r=BY[d,t,ratio]
                if ratio==1:lines.append(r'\rowcolor{control}')
                lines.append(f"{label if j==0 else ''} & {ratio:.2f} & {float(r['psnr_mean']):.2f} & {float(r['ssim_mean']):.3f} & {float(r['lpips_mean']):.3f} & {float(r['psnr_delta_vs_correct_mean']):+.3f}"+r'\\')
            if i<4:lines.append(r'\midrule')
        lines.extend([r'\bottomrule',r'\end{tabular}',r'\end{table}',r'\clearpage']);parts.append('\n'.join(lines))
    return '\n'.join(parts)

def main():
    OUT.mkdir(parents=True,exist_ok=True);BUILD.mkdir(parents=True,exist_ok=True)
    tex=(ROOT/'tools/report_template.tex').read_text().replace('%%CONTROL_TABLE%%',control_table()).replace('%%HIGHLIGHT_TABLE%%',highlights()).replace('%%FULL_TABLES%%',full_tables())
    source=OUT/'robust-flower-report.tex';source.write_text(tex)
    for _ in range(2):
        result=subprocess.run(['/Library/TeX/texbin/pdflatex','-interaction=nonstopmode','-halt-on-error',f'-output-directory={BUILD}',source.name],cwd=OUT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (BUILD/'build-output.txt').write_text(result.stdout)
        if result.returncode:raise RuntimeError(result.stdout[-7000:])
    shutil.copy2(BUILD/'robust-flower-report.pdf',OUT/'robust-flower-report.pdf')
    print(OUT/'robust-flower-report.pdf')

if __name__=='__main__':main()
