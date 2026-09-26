"""Preserve raw export; create portable kinematic XML with explicit limitations."""
from pathlib import Path
import sys,shutil,xml.etree.ElementTree as ET
root=Path(sys.argv[1]);src=root/'robot.urdf';raw=root/'robot.onshape-raw.urdf'
shutil.copy2(src,raw)
tree=ET.parse(raw);robot=tree.getroot()
for link in robot.findall('link'):
    for tag in ['inertial','origin']:
        for e in link.findall(tag):link.remove(e)
for j in robot.findall('joint'):
    if j.attrib['type']=='fixed':
        for tag in ['axis','limit']:
            for e in j.findall(tag):j.remove(e)
for mesh in robot.findall('.//mesh'):
    mesh.set('filename',mesh.attrib['filename'].removeprefix('package://'))
ET.indent(tree,space='  ');tree.write(src,encoding='utf-8',xml_declaration=True)
print(src, len(robot.findall('link')),'links',len(robot.findall('joint')),'joints')
