#!/usr/bin/env python3
"""Publication figures from the completed CSVs and saved images. No inference."""
from pathlib import Path
import csv
import json
import hashlib
import os

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'artifacts/build/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from matplotlib.patches import Rectangle
from PIL import Image
import numpy as np

RESULTS = ROOT / 'artifacts/experiments/main'
OUT = ROOT / 'artifacts/figures/publication'
PDF = ROOT / 'artifacts/build/redesign/figure-pdf'
TASKS = ['denoising', 'gaussian_deblurring', 'super_resolution', 'random_inpainting', 'box_inpainting']
LABELS = ['Denoising', 'Gaussian deblurring', 'Super-resolution', 'Random inpainting', 'Box inpainting']
DATASETS = ['celeba', 'afhq_cat']
NAMES = {'celeba': 'CelebA', 'afhq_cat': 'AFHQ-Cat'}
COLORS = ['#3155A4', '#C55A25', '#8B5AA6', '#008477', '#AD4266']
MARKERS = ['o', 's', '^', 'D', 'v']
RATIOS = [.5, .75, 1., 1.25, 1.5]
INK = '#20252C'
GRAY = '#56616D'

def read_csv(name):
    with (RESULTS / name).open() as f:
        return list(csv.DictReader(f))

SUMMARY = read_csv('summary.csv')
METRICS = read_csv('metrics.csv')
BY = {(r['dataset'], r['task'], float(r['assumed_to_true_sigma'])): r for r in SUMMARY}

def setup():
    OUT.mkdir(parents=True, exist_ok=True)
    PDF.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 11,
        'axes.titlesize': 13, 'axes.titleweight': 'bold',
        'axes.labelsize': 11, 'axes.labelcolor': INK, 'text.color': INK,
        'xtick.color': GRAY, 'ytick.color': GRAY,
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.edgecolor': '#929BA5', 'axes.linewidth': .75,
        'grid.color': '#D8DDE3', 'grid.linewidth': .65,
        'mathtext.fontset': 'dejavusans', 'svg.fonttype': 'none',
        'savefig.facecolor': 'white', 'figure.facecolor': 'white',
    })

def save(fig, name, vector=True):
    fig.savefig(OUT / f'{name}.png', dpi=300, bbox_inches='tight', pad_inches=.15)
    fig.savefig(PDF / f'{name}.pdf', bbox_inches='tight', pad_inches=.15)
    if vector:
        fig.savefig(OUT / f'{name}.svg', bbox_inches='tight', pad_inches=.15)
    plt.close(fig)

def heading(fig, title, subtitle):
    fig.suptitle(title, x=.5, y=.99, fontsize=17, fontweight='bold')
    fig.text(.5, .923, subtitle, ha='center', va='top', fontsize=10.5, color=GRAY)

def response(metric, number):
    label = {'psnr': 'PSNR', 'ssim': 'SSIM', 'lpips': 'LPIPS'}[metric]
    unit = ' (dB)' if metric == 'psnr' else ''
    direction = 'Higher is better' if metric != 'lpips' else 'Lower is better'
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 5.55), sharey=True)
    fig.subplots_adjust(left=.085, right=.98, bottom=.27, top=.81, wspace=.12)
    heading(fig, f'{label} response to an incorrect assumed noise level',
            f'Mean paired change from the correctly specified reconstruction; 20 images per dataset')
    all_lo, all_hi = [], []
    for ax, dataset in zip(axes, DATASETS):
        for task, name, color, marker in zip(TASKS, LABELS, COLORS, MARKERS):
            rows = [BY[dataset, task, r] for r in RATIOS]
            y = np.array([float(r[f'{metric}_delta_vs_correct_mean']) for r in rows])
            e = np.array([float(r[f'{metric}_delta_vs_correct_ci95']) for r in rows])
            all_lo.extend(y-e); all_hi.extend(y+e)
            ax.errorbar(RATIOS, y, yerr=e, color=color, marker=marker, ms=5.5,
                        linewidth=1.9, capsize=2.5, elinewidth=.9, label=name, zorder=3)
        ax.axhline(0, color='#444C56', lw=.95, zorder=1)
        ax.axvline(1, color='#7C858F', ls=(0,(3,3)), lw=.9, zorder=1)
        ax.set_title(NAMES[dataset], pad=10)
        ax.set_xticks(RATIOS, ['0.50','0.75','1.00','1.25','1.50'])
        ax.set_xlim(.46,1.54)
        ax.set_xlabel(r'Assumed / true standard deviation, $r=\sigma_a/\sigma_{\rm true}$', labelpad=9)
        ax.grid(axis='y')
        ax.tick_params(labelleft=True)
    lo, hi = min(all_lo), max(all_hi)
    pad = (hi-lo)*.10
    axes[0].set_ylim(lo-pad,hi+pad)
    axes[0].set_ylabel(f'Mean change in {label}{unit}\n{direction}', labelpad=10)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.5,.072), ncol=5,
               frameon=False, fontsize=10, handlelength=2, columnspacing=1.5)
    fig.text(.5,.025,'Error bars: approximate 95% CI of paired differences (mean ± 1.96 SE). '
             'r = 1: correct noise level; r < 1: underestimated; r > 1: overestimated.',
             ha='center',fontsize=9,color=GRAY)
    save(fig, f'{number:02d}_{metric}_response')

def heatmap():
    fig, axes = plt.subplots(1,2,figsize=(12.6,6.2))
    fig.subplots_adjust(left=.17,right=.9,top=.78,bottom=.18,wspace=.45)
    heading(fig,'Task dependence of noise-level mismatch',
            'Mean paired PSNR change (dB) relative to r = 1; 20 images in every cell')
    ratios=[.5,.75,1.25,1.5]
    arrays=[np.array([[float(BY[d,t,r]['psnr_delta_vs_correct_mean']) for r in ratios] for t in TASKS]) for d in DATASETS]
    limit=max(abs(a).max() for a in arrays)
    cmap=LinearSegmentedColormap.from_list('loss_gain',['#A63F46','#FAFAFA','#296D9B'])
    for ax,d,a in zip(axes,DATASETS,arrays):
        im=ax.imshow(a,cmap=cmap,norm=TwoSlopeNorm(0,-limit,limit),aspect='auto')
        ax.set_title(NAMES[d],pad=12)
        ax.set_xticks(range(4),['0.50','0.75','1.25','1.50'])
        ax.set_yticks(range(5),LABELS)
        ax.set_xlabel(r'Assumed / true standard deviation, $r$',labelpad=10)
        for i in range(5):
            for j in range(4):
                value='0.00' if abs(a[i,j])<.005 else f'{a[i,j]:+.2f}'
                ax.text(j,i,value,ha='center',va='center',fontweight='bold',fontsize=12,
                        color='white' if abs(a[i,j])>.60*limit else INK)
        ax.set_xticks(np.arange(-.5,4,1),minor=True);ax.set_yticks(np.arange(-.5,5,1),minor=True)
        ax.grid(which='minor',color='white',linewidth=2);ax.tick_params(which='both',length=0)
        for sp in ax.spines.values():sp.set_visible(False)
    cax=fig.add_axes([.935,.19,.018,.58]);cb=fig.colorbar(im,cax=cax)
    cb.set_label('Mean ΔPSNR (dB)')
    fig.text(.5,.065,'Blue: higher PSNR than the control. Red: lower PSNR. '
             'The correct-noise column is zero by definition and is omitted.',ha='center',fontsize=10,color=GRAY)
    save(fig,'04_psnr_mismatch_map')

def directory(dataset,task):
    paths=sorted((RESULTS/'reconstructions'/dataset/task).glob('image_*'))
    if len(paths)!=1:raise ValueError(paths)
    return paths[0]

def image_axes(ax,path,border=False):
    ax.imshow(Image.open(path),interpolation='nearest')
    ax.set_xticks([]);ax.set_yticks([])
    for s in ax.spines.values():s.set_visible(True);s.set_linewidth(1.8 if border else .5);s.set_edgecolor('#3155A4' if border else '#CCD2D9')

def image_metric(dataset,task,ratio):
    rows=[r for r in METRICS if r['dataset']==dataset and r['task']==task and int(r['image_position'])==7 and float(r['assumed_to_true_sigma'])==ratio]
    if len(rows)!=1:raise ValueError('Image metric mismatch')
    return rows[0]

def qualitative(dataset,number):
    fig,axes=plt.subplots(5,7,figsize=(11.8,10.7))
    fig.subplots_adjust(left=.125,right=.992,top=.87,bottom=.095,wspace=.09,hspace=.35)
    fig.suptitle(f'{NAMES[dataset]} reconstructions across all five inverse problems',y=.985,fontsize=18,fontweight='bold')
    image_id=image_metric(dataset,TASKS[0],1)['image']
    fig.text(.5,.947,f'Fixed example: {image_id}\nEach row uses the same measurement and source-noise draws',ha='center',va='top',fontsize=11,color=GRAY,linespacing=1.5)
    columns=[('ground_truth.png','Ground truth'),('measurement.png','Measurement')]+[(f'sigma_ratio_{r:g}.png',f'r = {r:.2f}'+('\n(correct)' if r==1 else '')) for r in RATIOS]
    for i,(task,label) in enumerate(zip(TASKS,LABELS)):
        for j,(filename,col) in enumerate(columns):
            ax=axes[i,j];image_axes(ax,directory(dataset,task)/filename,j==4)
            if i==0:ax.set_title(col,fontsize=11,pad=8,fontweight='bold' if j==4 else 'normal')
            if j==0:
                short=label.replace('Gaussian ','Gaussian\n').replace('Random ','Random\n').replace('Box ','Box\n').replace('Super-resolution','Super-\nresolution')
                ax.text(-.17,.5,short,transform=ax.transAxes,ha='right',va='center',fontsize=11,fontweight='bold')
            if j>=2:
                row=image_metric(dataset,task,RATIOS[j-2])
                ax.set_xlabel(f"{float(row['psnr']):.2f} dB",fontsize=10.5,labelpad=5)
    fig.text(.5,.022,'Numbers below each reconstruction: individual-image PSNR in dB (higher is better).\n'
             r'$r=\sigma_a/\sigma_{\rm true}$. Blue frame: correct-noise control. Measurements are displayed in the image domain via $H^T y$.',
             ha='center',fontsize=9.5,color=GRAY,linespacing=1.6)
    save(fig,f'{number:02d}_{dataset}_reconstructions',vector=False)

def trajectory():
    root=RESULTS/'analysis_capture';meta=json.loads((root/'metadata.json').read_text())
    times=meta['trajectory_times']
    fig,axes=plt.subplots(5,5,figsize=(10,10.8))
    fig.subplots_adjust(left=.14,right=.97,top=.84,bottom=.10,wspace=.08,hspace=.13)
    fig.suptitle('Evolution of the FLOWER reconstruction trajectory',y=.985,fontsize=17,fontweight='bold')
    fig.text(.5,.946,f"CelebA denoising, image {meta['image']}    |    Same measurement and source-noise draws",ha='center',fontsize=10,color=GRAY)
    fig.text(.54,.902,r'Flow time $t$ (left to right)',ha='center',fontsize=12,fontweight='bold')
    for i,r in enumerate(RATIOS):
        for j,t in enumerate(times):
            ax=axes[i,j];image_axes(ax,root/'trajectory'/f'ratio_{r:g}'/f't_{t:g}.png',r==1)
            if i==0:ax.set_title(f't = {t:.1f}',fontsize=12,pad=9)
            if j==0:ax.text(-.13,.5,f'r = {r:.2f}',transform=ax.transAxes,ha='right',va='center',fontsize=11,fontweight='bold' if r==1 else 'normal')
    fig.text(.025,.48,'Assumed / true noise standard deviation',rotation=90,va='center',fontsize=11)
    fig.text(.5,.033,'Each tile is the stored trajectory state, not an intermediate clean-image estimate.\n'
             'The blue row is the correct-noise control. The final column shows the reconstructed image at t = 1.',ha='center',fontsize=10,color=GRAY,linespacing=1.6)
    save(fig,'07_reconstruction_trajectory',vector=False)

def internals(t,number):
    root=RESULTS/'analysis_capture'
    states=[('destination',r'1  Destination estimate $\hat{x}_1$'),('refined',r'2  Refined destination $\mu_t$'),('trajectory',r'3  Next state $x_{t+\Delta t}$')]
    fig,axes=plt.subplots(3,3,figsize=(9.2,8.6))
    fig.subplots_adjust(left=.16,right=.98,top=.82,bottom=.09,wspace=.16,hspace=.10)
    fig.suptitle(f'Inside FLOWER at flow time t = {t:.2f}',y=.985,fontsize=18,fontweight='bold')
    fig.text(.5,.94,'CelebA denoising, image 182734.jpg; 100 reconstruction steps',ha='center',fontsize=11,color=GRAY)
    for i,r in enumerate([.5,1,1.5]):
        for j,(state,label) in enumerate(states):
            ax=axes[i,j];image_axes(ax,root/'internals'/f'ratio_{r:g}'/f't_{t:g}'/f'{state}.png',r==1)
            if i==0:ax.set_title(label,fontsize=11,pad=13)
            if j==0:ax.text(-.13,.5,f'r = {r:.2f}',transform=ax.transAxes,ha='right',va='center',fontsize=12,fontweight='bold' if r==1 else 'normal')
    fig.text(.025,.48,'Assumed / true noise standard deviation',rotation=90,va='center',fontsize=11)
    fig.text(.5,.025,'Read each row from left to right. Only the second step uses the assumed noise level directly.\n'
             'The third column includes newly sampled source noise; it need not look cleaner than the refined destination.',
             ha='center',fontsize=9.5,color=GRAY,linespacing=1.6)
    save(fig,f'{number:02d}_internal_states_t{str(t).replace(".","")}',vector=False)

def per_task(task,label):
    fig,axes=plt.subplots(1,3,figsize=(12.6,4.65))
    fig.subplots_adjust(left=.07,right=.98,top=.75,bottom=.25,wspace=.35)
    heading(fig,f'{label}: comparison across reconstruction metrics','Mean paired differences from r = 1; approximate 95% confidence intervals')
    for ax,metric in zip(axes,['psnr','ssim','lpips']):
        for d,color,marker in zip(DATASETS,['#3155A4','#C55A25'],['o','s']):
            rows=[BY[d,task,r] for r in RATIOS]
            ax.errorbar(RATIOS,[float(r[f'{metric}_delta_vs_correct_mean']) for r in rows],
                        yerr=[float(r[f'{metric}_delta_vs_correct_ci95']) for r in rows],color=color,
                        marker=marker,lw=1.8,capsize=3,ms=5,label=NAMES[d])
        ax.axhline(0,color='#666666',lw=.8);ax.axvline(1,color='#888888',ls='--',lw=.8)
        ax.set_title(metric.upper()+(' (higher is better)' if metric!='lpips' else ' (lower is better)'),fontsize=11)
        ax.set_xticks(RATIOS,['.50','.75','1.00','1.25','1.50']);ax.set_xlabel(r'Assumed / true standard deviation, $r$',fontsize=10)
        ax.set_ylabel('Mean Δ'+metric.upper()+(' (dB)' if metric=='psnr' else ''));ax.grid(axis='y')
    fig.legend(*axes[0].get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.04),ncol=2,frameon=False)
    save(fig,f'task_{task}')

def main():
    setup()
    assert len(METRICS)==1000 and len(SUMMARY)==50
    for i,m in enumerate(['psnr','ssim','lpips'],1):response(m,i)
    heatmap();qualitative('celeba',5);qualitative('afhq_cat',6);trajectory()
    for t,n in [(.75,8),(.25,9),(.5,10)]:internals(t,n)
    for t,label in zip(TASKS,LABELS):per_task(t,label)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in RESULTS.glob('*.csv')}
    (OUT/'provenance.json').write_text(json.dumps({'source':'artifacts/experiments/main','source_csv_sha256':hashes,
        'sample_count_per_group':20,'reconstruction_count':1000,'ci_method':'mean +/- 1.96 * sample SD / sqrt(20), paired per image',
        'generator':'tools/redesign_figures.py','inference_performed':False},indent=2)+'\n')
    print(f'Created 15 figures from existing results in {OUT}')

if __name__=='__main__':main()
