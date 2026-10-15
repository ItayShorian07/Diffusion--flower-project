#!/usr/bin/env python3
"""Add explicit per-point native OOXML error bars from the stored paired CIs."""
from pathlib import Path
import sys,json,re,zipfile
from lxml import etree as E

NS='http://schemas.openxmlformats.org/drawingml/2006/chart'
def c(parent,name,**attrs):return E.SubElement(parent,'{'+NS+'}'+name,**{k:str(v) for k,v in attrs.items()})
source,destination,error_path=map(Path,sys.argv[1:4])
errors=json.loads(error_path.read_text())
with zipfile.ZipFile(source) as zin,zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as zout:
 charts=sorted([n for n in zin.namelist() if re.fullmatch(r'ppt/(?:slides/)?charts/chart\d+\.xml',n)],key=lambda x:int(re.search(r'chart(\d+)',x).group(1)))
 assert len(charts)==len(errors),(len(charts),len(errors))
 lookup=dict(zip(charts,errors))
 for item in zin.infolist():
  data=zin.read(item.filename)
  if item.filename in lookup:
   tree=E.fromstring(data);series=tree.findall('.//{'+NS+'}ser');assert len(series)==len(lookup[item.filename])
   for axis in tree.findall('.//{'+NS+'}valAx'):
    for old in axis.findall('{'+NS+'}crosses')+axis.findall('{'+NS+'}crossesAt'):axis.remove(old)
    lower=axis.find('{'+NS+'}scaling/{'+NS+'}min')
    cross=E.Element('{'+NS+'}crossesAt',val=lower.get('val') if lower is not None else '0')
    index=next((i+1 for i,ch in enumerate(axis) if E.QName(ch).localname=='crossAx'),len(axis))
    axis.insert(index,cross)
   for axis in tree.findall('.//{'+NS+'}catAx'):
    tick=axis.find('{'+NS+'}tickLblPos')
    if tick is None:
     tick=E.Element('{'+NS+'}tickLblPos',val='low')
     index=next((i for i,ch in enumerate(axis) if E.QName(ch).localname in ('spPr','txPr','crossAx')),len(axis))
     axis.insert(index,tick)
    else:tick.set('val','low')
   for ser,values in zip(series,lookup[item.filename]):
    for old in ser.findall('{'+NS+'}errBars'):ser.remove(old)
    bars=E.Element('{'+NS+'}errBars');c(bars,'errDir',val='y');c(bars,'errBarType',val='both');c(bars,'errValType',val='cust');c(bars,'noEndCap',val=0)
    for side in ['plus','minus']:
     lit=c(c(bars,side),'numLit');c(lit,'formatCode').text='0.0000';c(lit,'ptCount',val=len(values))
     for i,value in enumerate(values):c(c(lit,'pt',idx=i),'v').text=str(value)
    # ECMA schema places errBars before cat/val in a line series.
    first=next((j for j,ch in enumerate(ser) if E.QName(ch).localname in ('cat','val')),len(ser));ser.insert(first,bars)
   data=E.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True)
  zout.writestr(item,data)
print(f'Added native paired confidence intervals to {len(charts)} charts')
