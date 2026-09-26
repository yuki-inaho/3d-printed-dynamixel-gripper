from pathlib import Path
import json,hashlib,sys,shutil,xml.etree.ElementTree as ET
import numpy as np
import trimesh
from scipy.spatial import cKDTree
base=Path(__file__).resolve().parent.parent/'outputs'
a=base/'robot';b=base/'rebuild/robot'
for name in ['pg3_states.py','validate_robot.py']:shutil.copy2(a/name,b/name)
checks={}
for p in sorted((a/'assets').glob('*.stl')):
    q=b/'assets'/p.name
    ma=trimesh.load_mesh(p,process=False);mb=trimesh.load_mesh(q,process=False)
    va=ma.vertices;vb=mb.vertices
    err=float(max(cKDTree(va).query(vb)[0].max(),cKDTree(vb).query(va)[0].max()))
    assert err<1e-7,(p.name,err)
    area_delta=abs(float(ma.area-mb.area));assert area_delta<1e-8,(p.name,area_delta)
    checks[p.stem]=dict(sha256_identical=hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256(q.read_bytes()).digest(),max_bidirectional_vertex_distance_m=err,surface_area_delta_m2=area_delta,triangles=[len(ma.faces),len(mb.faces)])
ra=ET.parse(a/'robot.urdf').getroot();rb=ET.parse(b/'robot.urdf').getroot()
topo=lambda r:sorted((j.get('name'),j.get('type'),j.find('parent').get('link'),j.find('child').get('link')) for j in r.findall('joint'))
assert topo(ra)==topo(rb)
sys.path.insert(0,str(a))
from validate_robot import origin
joint_error=0.;rotation_error=0.
for ja in ra.findall('joint'):
    jb=next(j for j in rb.findall('joint') if j.get('name')==ja.get('name'))
    rotation_error=max(rotation_error,float(np.max(np.abs(origin(ja.find('origin'))[:3,:3]-origin(jb.find('origin'))[:3,:3]))))
    for tag,attrs in [('origin',['xyz','rpy']),('axis',['xyz']),('limit',['lower','upper'])]:
        ea,eb=ja.find(tag),jb.find(tag)
        if ea is None:assert eb is None;continue
        for attr in attrs:
            if attr not in ea.attrib:continue
            aa=np.fromstring(ea.get(attr),sep=' ');bb=np.fromstring(eb.get(attr),sep=' ')
            # RPY +/-pi are equivalent; compare rotation matrices separately below.
            if attr!='rpy':joint_error=max(joint_error,float(np.max(np.abs(aa-bb))))
assert joint_error<1e-7,joint_error
assert rotation_error<2e-5,rotation_error
report=dict(status='PASS_WITH_EXPORT_ROUNDING',independent_source_reimport=True,topology_identical=True,mesh_comparison=checks,max_joint_translation_axis_limit_difference=joint_error,max_joint_rotation_matrix_difference=rotation_error)
(base/'rebuild/comparison.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
