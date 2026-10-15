import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const RUNTIME='/Users/Itays/.cache/codex-runtimes/codex-primary-runtime/dependencies';
process.env.RUNTIME_NODE_MODULES ??= path.join(RUNTIME,'node/node_modules');
const require=createRequire(path.join(process.env.RUNTIME_NODE_MODULES,'__loader.cjs'));
const {GlobalFonts}=require('@napi-rs/canvas');
const artifactRequire=createRequire(require.resolve('@oai/artifact-tool'));
const {FontLibrary}=artifactRequire('skia-canvas');
const fontPaths=[];
for(const suffix of ['Regular','Bold','Italic','BoldItalic']) {
  const fontPath=`/usr/local/texlive/2025/texmf-dist/fonts/opentype/google/roboto/RobotoCondensed-${suffix}.otf`;
  GlobalFonts.registerFromPath(fontPath,'Roboto Condensed');
  fontPaths.push(fontPath);
}
FontLibrary.use('Roboto Condensed',fontPaths);
const {Presentation,PresentationFile,FileBlob}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')));
const SKILL='/Users/Itays/.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations';
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')));
const BUILD=path.join(ROOT,'artifacts/build/redesign/presentation');
const OUT=path.join(ROOT,'artifacts/presentation/robust-flower-results.pptx');
const REF='/Users/Itays/Library/CloudStorage/OneDrive-Technion/Documents/לימודים/טכניון/סמסטר ב 2026/difuzia/flower presentation.pdf';
const F='Roboto Condensed';
const C={blue:'#303EAD',pale:'#ECEEFF',ink:'#222222',gray:'#5B616A',white:'#FFFFFF',grid:'#D5D8DF'};
const W=1000,H=750;
const p=Presentation.create({slideSize:{width:W,height:H}});
const datasetNames={celeba:'CelebA',afhq_cat:'AFHQ-Cat'};
const tasks=['denoising','gaussian_deblurring','super_resolution','random_inpainting','box_inpainting'];
const labels=['Denoising','Gaussian deblurring','Super-resolution','Random inpainting','Box inpainting'];
const colors=['#3155A4','#C55A25','#8B5AA6','#008477','#AD4266'];
const ratios=[.5,.75,1,1.25,1.5];
const source='artifacts/experiments/main';
function parseCsv(s){const [h,...r]=s.trim().split(/\r?\n/).map(l=>l.split(','));return r.map(v=>Object.fromEntries(h.map((k,i)=>[k,v[i]])));}
const rows=parseCsv(await fs.readFile(path.join(ROOT,source,'summary.csv'),'utf8'));
const raw=parseCsv(await fs.readFile(path.join(ROOT,source,'metrics.csv'),'utf8'));
const get=(d,t,r)=>rows.find(x=>x.dataset===d&&x.task===t&&Number(x.assumed_to_true_sigma)===r);
const imageRow=(d,t,r)=>raw.find(x=>x.dataset===d&&x.task===t&&Number(x.image_position)===7&&Number(x.assumed_to_true_sigma)===r);
const chartErrors=[];const chartOwners=[],tableOwners=[];
await fs.mkdir(BUILD,{recursive:true});

function rect(s,x,y,w,h,fill,shadow=false,stroke='none'){
 const o=s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:stroke,width:stroke==='none'?0:1}});
 if(shadow)o.shadow='2px 4px 3px #000000/25';return o;
}
function text(s,value,x,y,w,h,size=27,color=C.ink,bold=false,align='left'){
 const o=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 o.text=value;o.text.style={typeface:F,fontSize:size,color,bold,alignment:align,verticalAlignment:'middle',autoFit:'none',wrap:true};return o;
}
function slide(title){const s=p.slides.add();s.background.fill=C.white;rect(s,0,0,W,76,C.blue);text(s,title,35,10,930,55,39,C.white);return s;}
function note(s,body){s.speakerNotes.textFrame.setText(body+'\n\nSources: FLOWER paper (local Flower_main.pdf); config/robustness.json; artifacts/experiments/main/metrics.csv and summary.csv.');}
function foot(s,content){text(s,content,40,709,920,24,15,C.gray);}
function box(s,title,body,x,y,w,h,size=27){rect(s,x,y,w,h,C.pale,true);rect(s,x,y,w,40,C.blue);text(s,title,x+13,y+3,w-26,33,27,C.white);if(body)text(s,body,x+15,y+51,w-30,h-64,size);}
async function image(s,relative,x,y,w,h,alt){const file=path.isAbsolute(relative)?relative:path.join(ROOT,relative);s.images.add({blob:await fs.readFile(file),contentType:'image/png',position:{left:x,top:y,width:w,height:h},fit:'contain',alt});}
async function eq(s,name,x,y,w,h){await image(s,`artifacts/build/report-equations/${name}.png`,x,y,w,h,name);}
async function imgDir(d,t){const root=path.join(ROOT,source,'reconstructions',d,t);const names=(await fs.readdir(root)).filter(n=>n.startsWith('image_'));return path.join(root,names[0]);}

function table(s,values,x,y,w,h,widths){const tab=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,values,columnTracks:widths.map(value=>({mode:'fr',value}))});
 tab.styleOptions={headerRow:true,bandedRows:false};tab.borders.assign({style:'solid',fill:'#D2D5E8',width:.65});
 tab.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length}).assign({textStyle:{typeface:F,fontSize:21,color:C.ink},margins:{top:8,bottom:8,left:10,right:10},anchor:'middle'});
 for(let j=0;j<values[0].length;j++)tab.getCell(0,j).fill=C.blue;
 tab.cells.block({row:0,column:0,rowCount:1,columnCount:values[0].length}).assign({textStyle:{typeface:F,fontSize:22,color:C.white}});
 tableOwners.push(p.slides.items.length);return tab;
}

function chart(s,d,metric,x,y,w,h,{legend=true,title=true,min,max,step}={}){
 const metricName=metric.toUpperCase();
 const series=tasks.map((t,i)=>({name:labels[i],values:ratios.map(r=>Number(Number(get(d,t,r)[`${metric}_delta_vs_correct_mean`]).toFixed(6))),
   line:{style:'solid',fill:colors[i],width:2.4},marker:{symbol:['circle','square','triangle','diamond','star'][i],size:6}}));
 const c=s.charts.add('line',{position:{left:x,top:y,width:w,height:h},title:title?datasetNames[d]+' '+metricName:'Paired effect of the assumed noise level',
  titleTextStyle:{typeface:F,fontSize:25,fill:C.ink,bold:true},categories:ratios.map(r=>r.toFixed(2)),series,hasLegend:legend,
  lineOptions:{smooth:false,grouping:'standard'},legend:{position:'bottom',overlay:false,textStyle:{typeface:F,fontSize:17,fill:C.ink}},
  xAxis:{title:{text:'Assumed / true standard deviation, r',textStyle:{typeface:F,fontSize:19,fill:C.ink}},position:'bottom',textStyle:{typeface:F,fontSize:18,fill:C.ink},majorGridlines:null},
  yAxis:{title:{text:`Mean Δ${metricName}${metric==='psnr'?' (dB)':''}`,textStyle:{typeface:F,fontSize:19,fill:C.ink}},min,max,majorUnit:step,numberFormatCode:metric==='psnr'?'0.0':'0.00',textStyle:{typeface:F,fontSize:18,fill:C.ink},majorGridlines:{style:'solid',fill:C.grid,width:.7}},
  chartFill:C.white,plotAreaFill:C.white});
 applyPresentationChartFont(c,{fontFamily:F});
 chartOwners.push(p.slides.items.length);
 chartErrors.push(tasks.map(t=>ratios.map(r=>Number(Number(get(d,t,r)[`${metric}_delta_vs_correct_ci95`]).toFixed(6)))));
 return c;
}

// 1: the reference's minimal cover, in its original 4:3 proportions.
{
 const s=p.slides.add();s.background.fill=C.white;
 rect(s,55,150,890,224,C.blue,true);
 text(s,'Robust FLOWER Under\nNoise Model Mismatch',85,171,830,122,46,C.white,false,'center');
 text(s,'A controlled study of reconstruction quality',88,307,824,45,28,C.white,false,'center');
 text(s,'Itay Shorian',100,447,800,43,29,C.ink,false,'center');
 text(s,'Generative Learning and Diffusion Models',100,531,800,38,25,C.ink,false,'center');
 text(s,'October 2026',100,592,800,35,23,C.ink,false,'center');
 note(s,'Study of the completed 1,000-reconstruction experiment. The noise standard-deviation ratio controls the likelihood used by FLOWER.');
}
// 2–3: exactly two background slides on the paper.
{
 const s=slide('FLOWER: From a Measurement to a Clean Image');
 box(s,'Inverse Problem','We observe a degraded, noisy image and seek the underlying clean image.',44,126,440,218,27);
 await eq(s,'measurement',67,352,400,80);
 box(s,'The Image Prior','A pretrained flow model predicts a clean destination from the current trajectory state.',520,126,436,218,27);
 box(s,'Three Steps at Every Flow Time','1. Estimate the clean destination\n2. Refine it using the measurement\n3. Move to the next flow time',44,482,912,181,27);
 foot(s,'Pourya, El Rawas and Unser, FLOWER, ICLR 2026');
 note(s,'FLOWER combines the velocity network with a measurement-aware proximal correction. This slide summarizes the paper rather than the new robustness experiment.');
}
{
 const s=slide('The Noise Level Sets the Refinement Strength');
 box(s,'Destination Estimate','',44,118,912,142);await eq(s,'flow-path',70,169,860,72);
 box(s,'Measurement-Aware Refinement','',44,285,912,168);await eq(s,'proximal-objective',76,336,848,96);
 box(s,'Interpretation','A smaller assumed σ gives more weight to the measurement.\nA larger assumed σ gives more weight to the predicted destination.',44,482,912,170,26);
 foot(s,'The paper’s image benchmark uses Flower1-OT with γ = 0');
 note(s,'The endpoint covariance is approximated by ν_t² I. The refinement minimizes a Gaussian negative log density. Gamma=0 uses the refined mean, while source noise is still injected during progression. The OT practical setting does not meet all assumptions of the ideal posterior-sampling argument.');
}
{
 const s=slide('Our Research Question');
 box(s,'Noise Calibration','How does reconstruction quality change when FLOWER receives an incorrect noise standard deviation?',44,123,912,151,31);
 text(s,'r = σassumed / σtrue',100,300,800,53,37,C.blue,true,'center');
 table(s,[['r','0.50','0.75','1.00','1.25','1.50'],['Variance ratio','0.25','0.5625','1.00','1.5625','2.25']],65,385,870,110,[1.65,1,1,1,1,1]);
 box(s,'Paired Comparison','The image, measurement and source-noise draws are shared across all five ratios. We compare every result with its r = 1 control.',44,530,912,151,27);
 note(s,'Ratios refer to standard deviation, not variance. The actual measurements are generated once. Relative likelihood precision changes by 1/r².');
}
{
 const s=slide('Experimental Design');
 text(s,'20 fixed CelebA images + 20 fixed AFHQ-Cat images',44,104,912,48,31,C.blue,true,'center');
 table(s,[['Inverse problem','True σ','CelebA','AFHQ-Cat'],['Denoising','0.20','Identity','Identity'],['Gaussian deblurring','0.05','61 × 61, blur σ = 1','61 × 61, blur σ = 3'],['Super-resolution','0.05','2× subsampling','4× subsampling'],['Random inpainting','0.01','70% missing','70% missing'],['Box inpainting','0.05','40 × 40 central box','80 × 80 central box']],44,181,912,324,[1.6,.6,1.6,1.6]);
 text(s,'40 images × 5 problems × 5 ratios = 1,000 reconstructions',44,538,912,50,31,C.blue,true,'center');
 text(s,'PSNR ↑      SSIM ↑      LPIPS ↓',44,608,912,45,31,C.ink,false,'center');
 foot(s,'Same selected images throughout each dataset. Seed 2026. Noise σ is in model coordinates [-1, 1].');
 note(s,'Images were selected without replacement from the paper benchmark pools. CelebA resolution 128×128, AFHQ-Cat 256×256. The full step counts and metric implementation conventions are in the report.');
}
for(const d of ['celeba','afhq_cat']){
 const s=slide(`PSNR Response: ${datasetNames[d]}`);
 chart(s,d,'psnr',38,103,924,426,{title:false,min:-2.5,max:.75,step:.5});
 const msg=d==='celeba'?'Denoising loses 2.10 dB at r = 0.50. Super-resolution gains 0.42 dB. Random inpainting changes very little.':'Denoising improves by 0.35 dB at r = 0.75, but loses 1.25 dB at r = 0.50. Super-resolution gains 0.47 dB at r = 0.50.';
 box(s,'Main Observation',msg,44,557,912,120,26);
 foot(s,'Mean paired ΔPSNR vs r = 1. Higher is better. n = 20. Error bars: approximate 95% CI.');
 note(s,'Native editable chart. Values and paired 95% normal-approximation confidence intervals come directly from summary.csv. The zero value at ratio 1 is by construction. The lines join only the five measured ratios.');
}
for(const [metric,minimum,maximum,step,msg] of [
 ['ssim',-.15,.05,.05,'Underestimating noise can damage structure even when PSNR changes little. Super-resolution improves in both datasets.'],
 ['lpips',-.10,.10,.05,'At r = 0.50, AFHQ-Cat denoising improves LPIPS while PSNR and SSIM worsen. Perceptual and pixel fidelity can disagree.']]){
 const s=slide(`${metric.toUpperCase()} Response Across Both Datasets`);
 chart(s,'celeba',metric,27,108,467,408,{legend:false,min:minimum,max:maximum,step});
 chart(s,'afhq_cat',metric,509,108,467,408,{legend:false,min:minimum,max:maximum,step});
 for(let i=0;i<5;i++){const x=40+[0,158,378,576,774][i];rect(s,x,531,22,4,colors[i]);text(s,labels[i],x+29,517,[129,190,170,180,120][i],30,17.5);}
 box(s,'What the Metric Adds',msg,44,570,912,119,25);
 foot(s,`Mean paired change vs r = 1. ${metric==='lpips'?'Lower':'Higher'} is better. n = 20. Error bars: approximate 95% CI.`);
 note(s,'Both panels share the same vertical scale. LPIPS uses the public implementation convention, documented explicitly in the report appendix. Absolute LPIPS values should not be compared with a differently normalized pipeline.');
}
{
 const s=slide('All Tasks: Mean PSNR Change (dB)');
 text(s,'Cells compare a mismatched reconstruction with its r = 1 control',44,99,912,40,27,C.gray,false,'center');
 for(const [idx,d] of ['celeba','afhq_cat'].entries()){
  const x=44+idx*470;text(s,datasetNames[d],x,153,442,38,30,C.blue,true,'center');
  const values=[['Task','0.50','0.75','1.25','1.50'],...tasks.map((t,i)=>[labels[i].replace('Gaussian ','').replace('Random inpainting','Random inp.').replace('Box inpainting','Box inp.'),...[.5,.75,1.25,1.5].map(r=>{const v=Number(get(d,t,r).psnr_delta_vs_correct_mean);return Math.abs(v)<.005?'0.00':(v>0?'+':'')+v.toFixed(2);})])];
  const tab=table(s,values,x,208,442,329,[1.9,1,1,1,1]);
  tab.cells.block({row:0,column:0,rowCount:6,columnCount:5}).assign({textStyle:{typeface:F,fontSize:18,color:C.ink},margins:{top:8,bottom:8,left:5,right:5},anchor:'middle'});
  tab.cells.block({row:0,column:0,rowCount:1,columnCount:5}).assign({textStyle:{typeface:F,fontSize:19,color:C.white}});
  for(let i=1;i<6;i++)for(let j=1;j<5;j++){
   const v=Number(get(d,tasks[i-1],[.5,.75,1.25,1.5][j-1]).psnr_delta_vs_correct_mean);
   tab.getCell(i,j).fill=v<-.1?'#F6D9DC':v>.1?'#DDEAF5':'#F7F7FA';
  }
 }
 box(s,'Reading the Table','Positive values mean better PSNR. Overestimation lowers the mean in every tested dataset–task setting.',44,580,912,112,27);
 foot(s,'Each cell averages 20 paired image differences. The r = 1 column is zero by definition.');
 note(s,'Editable data tables. Background colors indicate sign and magnitude qualitatively, while exact numbers are printed. Unlike the report heatmap, this slide does not claim a continuous color scale.');
}
// One qualitative slide per inverse problem, all five ratios and both datasets.
const visualMessages=[
 'Underestimation preserves stronger fine-scale variation. Overestimation smooths it. The metrics determine whether this is detail or residual noise.',
 'The two datasets respond differently to underestimation. Kernel width and image content differ between them.',
 'Both datasets gain PSNR and SSIM and reduce LPIPS at r = 0.50 in the 20-image average.',
 'The reconstruction changes only slightly over this range. This task also has the smallest true noise level, σ = 0.01.',
 'The data term acts on observed pixels. The prior supplies the missing central region, and later iterations couple both regions.'
];
for(let k=0;k<tasks.length;k++){
 const t=tasks[k];const s=slide(`Visual Comparison: ${labels[k]}`);
 const titles=['Ground truth','Measurement','r = 0.50','r = 0.75','r = 1.00','r = 1.25','r = 1.50'];
 const cols=['ground_truth.png','measurement.png',...ratios.map(r=>`sigma_ratio_${r}.png`)];
 for(let j=0;j<7;j++)text(s,titles[j],45+j*132,111,126,34,18,j===4?C.blue:C.ink,j===4,'center');
 for(const [di,d] of ['celeba','afhq_cat'].entries()){
  const top=177+di*213;
  text(s,datasetNames[d],45,top-31,900,29,24,C.blue,true);
  const dir=await imgDir(d,t);
  for(let j=0;j<7;j++){
   if(j===4)rect(s,43+j*132,top-2,130,130,C.blue);
   await image(s,path.join(dir,cols[j]),45+j*132,top,126,126,`${datasetNames[d]} ${labels[k]} ${titles[j]}`);
   if(j>=2){const r=imageRow(d,t,ratios[j-2]);text(s,`${Number(r.psnr).toFixed(2)} / ${Number(r.ssim).toFixed(3)}\n${Number(r.lpips).toFixed(3)}`,45+j*132,top+132,126,40,17,C.ink,false,'center');}
  }
 }
 box(s,'Observation',visualMessages[k],44,586,912,109,24);
 foot(s,'Numbers: PSNR (dB) / SSIM, then LPIPS. Fixed examples; blue frame = correct noise. Measurement = Hᵀy.');
 note(s,'Displayed images are the saved qualitative examples: CelebA 182702.jpg and AFHQ pixabay_cat_001348.jpg. The metrics beneath tiles refer to these individual images. Text about aggregate behavior uses summary.csv. The same measurement is used within each row.');
}
{
 const s=slide('How Mismatch Changes the Trajectory');
 const times=[.2,.4,.6,.8,1];const shown=[.5,1,1.5];
 text(s,'CelebA denoising, image 182734.jpg',45,98,910,36,26,C.gray);
 text(s,'Flow time t',137,143,790,30,24,C.blue,false,'center');
 for(let j=0;j<5;j++)text(s,`t = ${times[j].toFixed(1)}`,138+j*163,178,143,32,22,C.ink,false,'center');
 for(let i=0;i<3;i++){const top=222+i*145;text(s,`r = ${shown[i].toFixed(2)}`,25,top+44,102,34,24,i===1?C.blue:C.ink,i===1);for(let j=0;j<5;j++){
  if(i===1)rect(s,138+j*163-2,top-2,137,137,C.blue);
  await image(s,`${source}/analysis_capture/trajectory/ratio_${shown[i]}/t_${times[j]}.png`,138+j*163,top,133,133,`Trajectory ratio ${shown[i]} time ${times[j]}`);
 }}
 foot(s,'Rows share measurement and source-noise draws. Final column: reconstruction. All five ratios are in the report.');
 note(s,'Stored diagnostic trajectory. The representative image is selected by the capture script using median image-level sensitivity. Early states are noisy by design. The ratio axis and the time axis are different experimental dimensions.');
}
{
 const s=slide('Inside the Three Steps at t = 0.75');
 const states=['destination','refined','trajectory'];const heads=['Destination estimate','Measurement refinement','Next trajectory state'];
 for(let j=0;j<3;j++)text(s,heads[j],145+j*273,116,252,35,25,C.blue,false,'center');
 for(let i=0;i<3;i++){const r=[.5,1,1.5][i],top=176+i*163;text(s,`r = ${r.toFixed(2)}`,26,top+49,105,40,25,i===1?C.blue:C.ink,i===1);for(let j=0;j<3;j++){
   const x=197+j*273;if(i===1)rect(s,x-2,top-2,151,151,C.blue);
   await image(s,`${source}/analysis_capture/internals/ratio_${r}/t_0.75/${states[j]}.png`,x,top,147,147,`${heads[j]} ratio ${r}`);
 }}
 foot(s,'CelebA denoising, image 182734.jpg. Step 2 uses σ directly. Step 3 adds source noise and advances time.');
 note(s,'The first-column differences can be induced by earlier refinements. Do not claim the mismatch only affects the second column: it acts directly there, and indirectly changes later network predictions.');
}
{
 const s=slide('Interpreting the Evidence');
 box(s,'Why the Forward Operator Matters','Denoising changes the measurement weight at every pixel. Masked and subsampled problems constrain only observed locations directly.',44,122,912,154,28);
 box(s,'Why Correct Noise Need Not Maximize PSNR','The practical solver uses a learned velocity and an approximate endpoint distribution. A different data weight can compensate for their errors on a finite sample.',44,304,912,170,28);
 box(s,'Limits of the Comparison','20 images per dataset and one paired seed sequence per image–task pair. Paper results use 100 images. Confidence intervals summarize image variation.',44,502,912,165,28);
 foot(s,'These results establish sensitivity on the tested sample; they do not identify a universal optimal noise ratio.');
 note(s,'Mechanistic explanations are interpretations of the refinement equation. The experiment does not isolate the cause of the super-resolution improvement. Task and true noise level vary together, so operator dependence is not a pure operator-only ablation.');
}
{
 const s=slide('Conclusions');
 box(s,'Sensitivity Depends on the Task','Denoising is the most sensitive setting. Random inpainting is nearly unchanged over the tested range.',44,124,912,139,30);
 box(s,'Overestimation Consistently Hurts Mean PSNR','Both r = 1.25 and r = 1.50 reduce mean PSNR in all ten dataset–task settings.',44,292,912,138,30);
 box(s,'Underestimation Has No Universal Outcome','Super-resolution improves in both datasets. Severe underestimation hurts denoising, and LPIPS can disagree with PSNR and SSIM.',44,459,912,171,30);
 text(s,'Noise calibration should be evaluated for the task and the metric.',44,660,912,38,28,C.blue,true,'center');
 note(s,'Conclusions are restricted to the five tested ratios and the fixed samples. No new reconstruction was run to produce these slides.');
}
{
 const s=slide('References and Reproducible Results');
 text(s,'M. Pourya, B. El Rawas and M. Unser\nFLOWER: A Flow-Matching Solver for Inverse Problems\nICLR 2026',54,130,892,126,29);
 text(s,'Y. Lipman et al.\nFlow Matching for Generative Modeling\nICLR 2023',54,294,892,116,28);
 box(s,'Project Results','Raw and paired metrics, all 50 summary rows, saved examples, and trajectory captures are in artifacts/experiments/main/.',44,458,912,148,27);
 text(s,'github.com/ItayShorian07/Diffusion--flower-project',44,644,912,40,25,C.blue,false,'center');
 note(s,'Scientific sources and experimental files are cited throughout the speaker notes. Report includes derivations, full result tables, and details of the LPIPS convention.');
}

const candidate=path.join(BUILD,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidate);
await fs.writeFile(path.join(BUILD,'chart-errors.json'),JSON.stringify(chartErrors));
const patched=path.join(BUILD,'candidate-with-ci.pptx');
const patch=spawnSync(path.join(RUNTIME,'python/bin/python3'),[path.join(ROOT,'tools/patch_chart_confidence.py'),candidate,patched,path.join(BUILD,'chart-errors.json')],{encoding:'utf8'});
if(patch.status!==0)throw new Error(patch.stderr||patch.stdout);
const finalPath=process.env.FLOWER_PPTX_OUTPUT || OUT;
await fs.mkdir(path.dirname(finalPath),{recursive:true});
await finalizePresentation({workspaceDir:ROOT,candidatePath:patched,finalPath,
 pythonExecutable:path.join(RUNTIME,'python/bin/python3'),
 integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),
 explicitTotalSlideCount:p.slides.items.length,
 requiredNativeChartOwnerSlides:[...new Set(chartOwners)],requiredNativeTableOwnerSlides:[...new Set(tableOwners)],
 materializeLiteralChartWorkbooks:true,verifyArtifactToolImport:true,
 layoutArgs:['--expected-slide-size-emu','9525000,7143750','--validate-heading-fit',
   ...[...new Set(tableOwners)].flatMap(n=>['--require-native-table-slide',String(n)])],
 // The PDF uses PostScript name RobotoCondensed-Regular; the font's actual
 // Office family is "Roboto Condensed". The strict reference validator does
 // not normalize this alias, so declare that exact family as the design font.
 fontPolicy:{basis:'design',families:[F]},
 receiptPath:path.join(BUILD,path.basename(finalPath)+'.'+Date.now()+'.validation.json')});
// Render the finalized package, with the exact reference font loaded in the renderer.
const finalPresentation=await PresentationFile.importPptx(await FileBlob.load(finalPath));
const renderDir=path.join(BUILD,'render');await fs.mkdir(renderDir,{recursive:true});
for(let i=0;i<finalPresentation.slides.items.length;i++){
 const preview=await finalPresentation.export({slide:finalPresentation.slides.items[i],format:'png',scale:1.6});
 await fs.writeFile(path.join(renderDir,`slide-${String(i+1).padStart(2,'0')}.png`),Buffer.from(await preview.arrayBuffer()));
}
await fs.writeFile(path.join(BUILD,'reference-style.json'),JSON.stringify({reference:REF,
 referenceSha256:crypto.createHash('sha256').update(await fs.readFile(REF)).digest('hex'),
 pdfPostscriptFamily:'RobotoCondensed',officeFamily:F,aspectRatio:'4:3'},null,2));
// Native Office-compatible rendering preserves custom chart confidence bars.
// Supply the reference font explicitly without installing anything system-wide.
const fontConfig=path.join(BUILD,'fonts.conf');
await fs.writeFile(fontConfig,`<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd"><fontconfig><dir>/usr/local/texlive/2025/texmf-dist/fonts/opentype/google/roboto</dir><dir>/System/Library/Fonts</dir><dir>/Library/Fonts</dir><cachedir>/private/tmp/flower-font-cache</cachedir></fontconfig>`);
const pdfExport=spawnSync(path.join(RUNTIME,'bin/override/soffice'),['--headless','--convert-to','pdf','--outdir',path.dirname(finalPath),finalPath],{encoding:'utf8',env:{...process.env,FONTCONFIG_FILE:fontConfig}});
if(pdfExport.status!==0)throw new Error(pdfExport.stderr||pdfExport.stdout);
console.log(JSON.stringify({finalPath,slides:p.slides.items.length,renderDir}));
