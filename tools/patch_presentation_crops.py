#!/usr/bin/env python3
"""Preserve explicit, editable scientific image crops in the exported PPTX."""
from pathlib import Path
import json
import sys
import zipfile
from lxml import etree as E

source, destination, manifest = map(Path, sys.argv[1:4])
groups = json.loads(manifest.read_text())
NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
A = '{' + NS['a'] + '}'
patched = 0
with zipfile.ZipFile(source) as archive, zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as output:
    for item in archive.infolist():
        selected = [g for g in groups if item.filename == f"ppt/slides/slide{g['slide']}.xml"]
        data = archive.read(item.filename)
        if selected:
            tree = E.fromstring(data)
            for group in selected:
                row = 0 if group['dataset'] == 'celeba' else 1
                crop_y = 234 + row * 277
                left, top, right, bottom = group['normalizedBounds']
                for column in range(7):
                    crop_x = 53 + column * 132
                    matches = []
                    for pic in tree.findall('.//p:pic', NS):
                        offset = pic.find('p:spPr/a:xfrm/a:off', NS)
                        if offset is not None and abs(int(offset.get('x')) / 9525 - crop_x) < .1 and abs(int(offset.get('y')) / 9525 - crop_y) < .1:
                            matches.append(pic)
                    assert len(matches) == 1, (item.filename, crop_x, crop_y, len(matches))
                    fill = matches[0].find('p:blipFill', NS)
                    crop = fill.find('a:srcRect', NS)
                    if crop is None:
                        crop = E.SubElement(fill, A + 'srcRect')
                    for key, value in zip(('l', 't', 'r', 'b'), (left, top, 1 - right, 1 - bottom)):
                        crop.set(key, str(round(value * 100000)))
                    patched += 1
            data = E.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True)
        output.writestr(item, data)
assert patched == 70, patched
print(f'Preserved {patched} native scientific image crops')
