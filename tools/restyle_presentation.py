#!/usr/bin/env python3
"""Apply the user's academic reference style while preserving native evidence.

Input: existing project PPTX. Output: a separately staged PPTX plus an edit
manifest for Artifact Tool review. Scientific images, crops, chart data,
confidence bars, workbooks and tables remain intact.
"""
from pathlib import Path
import argparse,copy,json,zipfile
from lxml import etree as E

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'artifacts/build/reference-style-redesign'
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
A='{'+NS['a']+'}'
BLUE='2D37AA';INK='2D2D2D';PALE='EBEBFF';EMU=9525

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--input',type=Path,default=B/'original.pptx')
 parser.add_argument('--output',type=Path,default=B/'candidate.pptx')
 args=parser.parse_args();B.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(args.input) as z:
  entries={x.filename:z.read(x.filename) for x in z.infolist()};infos=z.infolist()
 roots={i:E.fromstring(entries[f'ppt/slides/slide{i}.xml']) for i in range(1,21)}
 ops=[]
 def get(i,ident):
  tree=roots[i].find('p:cSld/p:spTree',NS)
  hits=[s for s in tree if s.find('.//p:cNvPr',NS) is not None and s.find('.//p:cNvPr',NS).get('id')==str(ident)]
  assert len(hits)==1,(i,ident);return hits[0]
 def frame(s):
  return s.find('p:xfrm',NS) if s.tag.endswith('graphicFrame') else s.find('p:spPr/a:xfrm',NS)
 def box(s):
  f=frame(s);o=f.find('a:off',NS);e=f.find('a:ext',NS);return [int(o.get('x'))/EMU,int(o.get('y'))/EMU,int(e.get('cx'))/EMU,int(e.get('cy'))/EMU]
 def op(i,ident,**kw):
  s=get(i,ident);oldtext='\n'.join(''.join(t.text or '' for t in p.findall('.//a:t',NS)) for p in s.findall('p:txBody/a:p',NS))
  typ='image' if s.tag.endswith('pic') else ('table' if s.find('.//a:tbl',NS) is not None else 'chart') if s.tag.endswith('graphicFrame') else ('textbox' if oldtext else 'shape')
  ops.append(dict(slide=i,shape_id=str(ident),kind=typ,old_box=box(s),old_text=oldtext,**kw))
 def delete(i,*ids):
  for ident in ids:op(i,ident,delete=True)
 def move(i,ident,x,y,w,h,**kw):op(i,ident,box=[x,y,w,h],**kw)
 def txt(i,ident,text=None,**kw):
  if text is not None:kw['text']=text
  op(i,ident,**kw)
 def panel(i,ids,x,y,w,h,heading,body,size=25):
  bg,band,head,content=ids;move(i,bg,x,y,w,h);move(i,band,x,y,w,40)
  move(i,head,x+13,y+3,w-26,33,text=heading,size=27,bold=False,color='FFFFFF',anchor='ctr')
  move(i,content,x+15,y+54,w-30,h-67,text=body,size=size,bold=False,color=INK,align='left',anchor='t')
 # Concise subject headings rather than repeated narrated takeaways.
 titles={2:'FLOWER',3:'Measurement refinement',4:'Noise-scale mismatch',5:'Experimental setup',6:'PSNR: CelebA',7:'PSNR: AFHQ-Cat',8:'SSIM',9:'LPIPS',10:'Paired PSNR changes',11:'Denoising',12:'Gaussian deblurring',13:'Super-resolution',14:'Random inpainting',15:'Box inpainting',16:'Reconstruction trajectory',17:'FLOWER at t = 0.75',18:'Discussion',19:'Conclusions',20:'References'}
 for i,t in titles.items():txt(i,2,t,size=39.5,bold=False)
 txt(1,3,'Reconstruction with an incorrect noise level',size=28,align='center')
 # Background: paired blocks and an ordinary list, as in the reference.
 panel(2,[3,4,5,6],44,135,430,220,'Inverse problem','Recover the clean image from a degraded, noisy measurement.',25)
 panel(2,[8,9,10,11],526,135,430,190,'Image prior','A pretrained flow model predicts the clean destination from the current trajectory state.',25)
 move(2,25,67,283,383,42)
 delete(2,12,13)
 move(2,14,44,419,912,38,text='Reconstruction steps',size=27,color=BLUE,bold=False)
 move(2,15,58,475,860,150,bullets=['Predict the clean destination.','Refine it using the measurement.','Advance to the next flow time.'],size=26,color=INK,anchor='t',align='left')
 # Keep the mathematical evidence, reduce the third decorative card.
 delete(3,11,12)
 move(3,13,44,496,912,38,text='Noise assumption',size=27,color=BLUE,bold=False)
 move(3,14,44,548,912,100,text='A smaller assumed σ gives more weight to the measurement.\nA larger assumed σ gives more weight to the predicted destination.',size=26,color=INK,anchor='t')
 txt(3,5,'Destination estimate',size=27,bold=False);txt(3,9,'Measurement refinement',size=27,bold=False)
 txt(4,5,'Question',size=27,bold=False)
 txt(4,6,'How sensitive is FLOWER to an incorrect measurement-noise level?',size=28,anchor='t')
 txt(4,7,subscript_ratio=True)
 txt(4,11,'Paired experiment',size=27,bold=False)
 txt(4,12,'Same image, measurement and random draws for every ratio.\nThe true noise level and noise structure stay fixed.',size=25,anchor='t')
 txt(5,3,'20 CelebA images and 20 AFHQ-Cat images',size=29,bold=False,color=INK)
 txt(5,10,'FLOWER-1 OT, γ = 0. Paired images, measurements and random draws.',size=22,color=INK)
 txt(5,5,size=30)
 move(5,6,44,599,350,40,size=26,color=INK,align='left',bold=False)
 move(5,11,434,599,522,40,size=26,color=INK,align='center',bold=False)
 move(5,12,434,646,522,33,size=23,color=INK,align='center',bold=False)
 # Charts with side commentary, matching the reference's results slides.
 for i in [6,7]:
  move(i,13,35,132,658,494)
  body=('Denoising\n−2.10 dB at r = 0.50\n\nSuper-resolution\n+0.42 dB at r = 0.50\n\nRandom inpainting changes very little.' if i==6 else 'Denoising\n+0.35 dB at r = 0.75\n−1.25 dB at r = 0.50\n\nSuper-resolution\n+0.47 dB at r = 0.50')
  panel(i,[4,5,6,7],715,166,241,330 if i==6 else 290,'At r < 1',body,24)
 for i in [8,9]:
  delete(i,15,16,17)
  move(i,25,27,126,467,408);move(i,26,509,126,467,408)
  for ident in [5,6,7,8,9,10,11,12,13,14]:
   s=get(i,ident);x,y,w,h=box(s);move(i,ident,x,y+18,w,h)
  body=('Underestimating noise can damage structure even when PSNR changes little.\nSuper-resolution improves in both datasets.' if i==8 else 'At r = 0.50, AFHQ-Cat denoising improves LPIPS while PSNR and SSIM worsen.\nPerceptual and pixel fidelity can disagree.')
  move(i,18,44,607,912,93,text=body,size=25,color=INK,anchor='t')
 delete(10,8,9,10)
 txt(10,3,'Paired changes relative to the r = 1 reconstruction',size=26,color=INK)
 move(10,11,44,593,912,90,text='Overestimation lowers mean PSNR in every tested dataset–task setting.',size=27,color=INK,anchor='t')
 # Retain every reconstruction, crop and metric; remove the repeated Finding strip.
 findings={11:'Lower assumed noise leaves more fine-scale variation. Higher assumed noise smooths it.',12:'The two domains respond differently. Blur kernels and image content also differ.',13:'At r = 0.50, all three metrics improve on average in both datasets.',14:'Changes are small across the tested ratios. This task also has the lowest true σ (0.01).',15:'The central region is unobserved. The prior and observed pixels jointly guide its reconstruction.'}
 for i in range(11,16):
  delete(i,38,39,40)
  txt(i,10,'CelebA',size=24,bold=False);txt(i,24,'AFHQ-Cat',size=24,bold=False)
  move(i,41,44,688,912,52,text=findings[i],size=22.5,color=INK,anchor='t')
 # Let the actual trajectory and internal states carry the explanation.
 delete(16,4)
 for j,ident in enumerate([5,6,7,8,9]):move(16,ident,138+j*163,150,145,32,size=22)
 for i,ident in enumerate([10,16,27]):move(16,ident,25,248+i*161,102,34,size=24)
 for row,ids in enumerate([[60,61,62,63,64],[67,69,71,73,75],[77,78,79,80,81]]):
  for j,ident in enumerate(ids):move(16,ident,138+j*163,195+row*161,145,145)
 for j,ident in enumerate([17,19,21,23,25]):move(16,ident,136+j*163,354,149,149)
 txt(17,3,'Predicted destination',size=25);txt(17,4,'Refined destination',size=25);txt(17,5,'Next state',size=25)
 for row,ids in enumerate([[38,39,40],[43,45,47],[49,50,51]]):
  for j,ident in enumerate(ids):move(17,ident,190+j*273,173+row*171,160,160)
 for j,ident in enumerate([11,13,15]):move(17,ident,188+j*273,342,164,164)
 for row,ident in enumerate([6,10,17]):move(17,ident,26,230+row*171,105,40,size=25)
 # Discussion: two possible mechanisms and one clearly separated scope block.
 panel(18,[3,4,5,6],44,130,565,218,'Measurement constraints','Denoising constrains every pixel.\nMasking and subsampling constrain observed locations.\nTrue noise levels also differ across tasks.',25)
 panel(18,[7,8,9,10],44,382,565,250,'Approximation error','A different data weight may partly compensate for prior or solver approximation errors.\n\nThe experiment does not isolate why underestimation sometimes improves the metrics.',25)
 panel(18,[11,12,13,14],642,130,314,502,'Limitations','',25)
 txt(18,14,bullets=['20 images per dataset, versus 100 in the paper.','One paired random sequence per image and task.','Task and true noise level vary together.'],size=24,color=INK,anchor='t')
 # A research conclusion, without stacked slogans and a second headline.
 delete(19,7,8,9,10,11,12,13,14)
 move(19,3,44,135,912,300);move(19,4,44,135,912,40)
 move(19,5,57,138,886,33,text='Noise-scale sensitivity',size=27,bold=False)
 move(19,6,62,195,870,225,bullets=['Denoising has the largest PSNR losses. Random inpainting changes very little.','Both r = 1.25 and r = 1.50 reduce mean PSNR in all ten dataset–task settings.','Underestimation improves super-resolution in both datasets. Severe underestimation harms denoising.','LPIPS can disagree with PSNR and SSIM.'],size=26,color=INK,bold=False,anchor='t')
 move(19,15,44,497,912,75,text='These conclusions apply to the tested images, tasks and noise ratios.',size=26,color=INK,bold=False)
 move(19,17,100,640,800,50,text='Thank you',size=32,color=INK,bold=False,align='center')
 delete(20,5,6)
 txt(20,3,size=27,anchor='t');txt(20,4,size=27,anchor='t')
 move(20,7,54,457,892,40,text='Project files',size=27,color=BLUE,bold=False)
 move(20,8,54,510,892,100,size=25,color=INK,anchor='t')
 move(20,9,44,650,912,40,size=25,color=BLUE)
 # Apply operations to original OOXML; do not round-trip scientific evidence.
 def settext(s,items,opts):
  tb=s.find('p:txBody',NS);assert tb is not None
  paras=tb.findall('a:p',NS);sample=paras[0] if paras else None
  run=sample.find('a:r/a:rPr',NS) if sample is not None else None
  default=copy.deepcopy(run) if run is not None else E.Element(A+'rPr')
  for p in paras:tb.remove(p)
  for text in items:
   p=E.SubElement(tb,A+'p');pr=E.SubElement(p,A+'pPr')
   if opts.get('bullets') is not None:
    pr.set('marL','285750');pr.set('indent','-190500');spc=E.SubElement(pr,A+'spcAft');E.SubElement(spc,A+'spcPts',val='650')
    bc=E.SubElement(pr,A+'buClr');E.SubElement(bc,A+'srgbClr',val=BLUE);E.SubElement(pr,A+'buChar',char='•')
   else:E.SubElement(pr,A+'buNone')
   r=E.SubElement(p,A+'r');r.append(copy.deepcopy(default));E.SubElement(r,A+'t').text=text
 def style(s,opts):
  tb=s.find('p:txBody',NS)
  if tb is None:return
  bp=tb.find('a:bodyPr',NS)
  if opts.get('anchor'):bp.set('anchor',opts['anchor'])
  for p in tb.findall('a:p',NS):
   pr=p.find('a:pPr',NS)
   if pr is None:pr=E.Element(A+'pPr');p.insert(0,pr)
   if opts.get('align'):pr.set('algn',{'left':'l','center':'ctr','right':'r'}[opts['align']])
   for prop in list(p.findall('a:r/a:rPr',NS))+list(p.findall('a:endParaRPr',NS))+list(pr.findall('a:defRPr',NS)):
    if 'size' in opts:prop.set('sz',str(round(opts['size']*75)))
    if 'bold' in opts:prop.set('b','1' if opts['bold'] else '0')
    if 'color' in opts:
     for sf in prop.findall('a:solidFill',NS):prop.remove(sf)
     sf=E.Element(A+'solidFill');E.SubElement(sf,A+'srgbClr',val=opts['color'])
     # DrawingML places fill before the font declarations.
     before=next((j for j,c in enumerate(prop) if E.QName(c).localname in {'effectLst','effectDag','highlight','uLnTx','uLn','uFillTx','uFill','latin','ea','cs','sym','hlinkClick','hlinkMouseOver','rtl','extLst'}),len(prop))
     prop.insert(before,sf)
 for o in ops:
  s=get(o['slide'],o['shape_id'])
  if o.get('delete'):s.getparent().remove(s);continue
  if 'box' in o:
   f=frame(s);off=f.find('a:off',NS);ext=f.find('a:ext',NS);x,y,w,h=o['box'];off.set('x',str(round(x*EMU)));off.set('y',str(round(y*EMU)));ext.set('cx',str(round(w*EMU)));ext.set('cy',str(round(h*EMU)))
  if 'text' in o:settext(s,o['text'].split('\n'),o)
  if 'bullets' in o:settext(s,o['bullets'],o)
  style(s,o)
  if o.get('subscript_ratio'):
   tb=s.find('p:txBody',NS)
   for par in tb.findall('a:p',NS):tb.remove(par)
   par=E.SubElement(tb,A+'p');E.SubElement(par,A+'pPr',algn='ctr')
   for text,baseline,size,italic in [('r = σ',0,2700,True),('assumed',-25000,1575,False),(' / σ',0,2700,True),('true',-25000,1575,False)]:
    run=E.SubElement(par,A+'r');pr=E.SubElement(run,A+'rPr',sz=str(size),baseline=str(baseline),b='0',i='1' if italic else '0');sf=E.SubElement(pr,A+'solidFill');E.SubElement(sf,A+'srgbClr',val=BLUE);E.SubElement(pr,A+'latin',typeface='Roboto Condensed');E.SubElement(run,A+'t').text=text
 # Match the supplied reference palette and restrained Beamer-style corners.
 for root in roots.values():
  for clr in root.findall('.//a:srgbClr',NS):
   if clr.get('val')=='303EAD':clr.set('val',BLUE)
   elif clr.get('val')=='ECEEFF':clr.set('val',PALE)
   elif clr.get('val')=='222222':clr.set('val',INK)
  for s in root.findall('p:cSld/p:spTree/p:sp',NS):
   fill=s.find('p:spPr/a:solidFill/a:srgbClr',NS);geom=s.find('p:spPr/a:prstGeom',NS)
   if fill is None or geom is None:continue
   x,y,w,h=box(s)
   if fill.get('val') in [BLUE,PALE] and h>60 and not (x==0 and y==0):
    geom.set('prst','roundRect');av=geom.find('a:avLst',NS)
    if av is None:av=E.SubElement(geom,A+'avLst')
    for child in list(av):av.remove(child)
    E.SubElement(av,A+'gd',name='adj',fmla='val 3600')
 for i,root in roots.items():entries[f'ppt/slides/slide{i}.xml']=E.tostring(root,xml_declaration=True,encoding='utf-8')
 # Short chart titles fit the reference's chart-and-commentary composition.
 for name,data in list(entries.items()):
  if '/charts/' not in name or not name.endswith('.xml') or '/_rels/' in name:continue
  root=E.fromstring(data);title=root.find('c:chart/c:title',NS)
  if title is None:continue
  texts=title.findall('.//a:t',NS)
  if not texts:continue
  num=int(Path(name).stem.replace('chart',''))
  texts[0].text='CelebA' if num in [1,3,5] else 'AFHQ-Cat'
  for t in texts[1:]:t.text=''
  entries[name]=E.tostring(root,xml_declaration=True,encoding='utf-8')
 args.output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(args.output,'w') as out:
  for info in infos:out.writestr(info,entries[info.filename])
 (B/'edit-manifest.json').write_text(json.dumps(ops,indent=2)+'\n')
 print(json.dumps({'output':str(args.output),'slides':20,'operations':len(ops)}))

if __name__=='__main__':main()
