"""Build deliverables, audit each exported STEP/STL and save the audit as JSON.
Run `python build_release.py`. Rendering is separately reproducible via make_previews.py.
"""
from design import *
from camera import optional_parts,stand,plate
from calibration import print_pose,retainer_variant,gauge,tongue
from guardrails import geometry,negative_tests
from assembly_reader import bounds
import trimesh,numpy as np,hashlib,time


def audit_mesh(path):
    raw=trimesh.load_mesh(path,process=False)
    # STL repeats vertices by construction; weld identical coordinates only, never repair faces.
    v,ix=np.unique(np.round(raw.vertices,6),axis=0,return_inverse=True)
    t=trimesh.Trimesh(v,ix[raw.faces],process=False)
    counts=np.bincount(t.edges_unique_inverse)
    data={'vertices':len(v),'triangles':len(t.faces),'watertight':bool(t.is_watertight),'winding_consistent':bool(t.is_winding_consistent),'volume_mm3':float(t.volume),'boundary_edges':int(np.sum(counts==1)),'nonmanifold_edges':int(np.sum(counts>2)),'zero_area_triangles':int(np.sum(t.area_faces<1e-10)),'bounds_mm':t.bounds.tolist()}
    data['pass']=data['watertight'] and data['winding_consistent'] and data['volume_mm3']>0 and not(data['boundary_edges'] or data['nonmanifold_edges'] or data['zero_area_triangles'])
    return data

def step_check(path,original):
    s=cq.importers.importStep(str(path)).val()
    v=s.Volume();v0=original.Volume()
    d={'valid':bool(s.isValid()),'solids':len(s.Solids()),'original_solids':len(original.Solids()),'volume_error_mm3':abs(v-v0),'bbox_max_error_mm':float(np.max(np.abs(np.array(bounds(s))-bounds(original))))}
    d['pass']=d['valid'] and d['solids']==d['original_solids'] and d['volume_error_mm3']<.01 and d['bbox_max_error_mm']<1e-4
    return d

def build():
    start=time.monotonic();m=Model();geometry(m)
    result={'revision':P.revision,'guardrails':{'positive':True,'negative_tests':negative_tests(m)},'stl':{},'step':{}}
    shapes=m.printed.copy()
    shapes.update({'07_camera_stand':stand(),'08_camera_plate':plate(),'09_fit_gauge':gauge(),'10_fit_tongue':tongue(),'02_retainer_total_gap_0p5':retainer_variant(.5),'02_retainer_total_gap_0p9':retainer_variant(.9)})
    inventory=[]
    qty={'01_frame':1,'02_retainer':2,'03_jaw':2,'04_crank':1,'05_link':2,'06_motor_mount':1,'07_camera_stand':1,'08_camera_plate':1,'09_fit_gauge':1,'10_fit_tongue':1}
    for n,s in shapes.items():
        if not s.isValid() or len(s.Solids())!=1:raise RuntimeError(f'{n}: not a single valid solid')
        path=ROOT/'CAD/parts'/f'{n}.step';cq.exporters.export(s,str(path));result['step'][str(path.relative_to(ROOT))]=step_check(path,s)
        q=print_pose(n,s);mp=ROOT/'STL'/f'{n}.stl';cq.exporters.export(q,str(mp),tolerance=.04,angularTolerance=.15);result['stl'][mp.name]=audit_mesh(mp)
        inventory.append({'id':n,'quantity':qty.get(n,2),'category':'core' if n in m.printed else ('calibration' if n.startswith(('09','10')) else 'optional' if n.startswith(('07','08')) else 'alternative'),'volume_mm3':s.Volume(),'print_bbox_mm':bounds(q),'support':'localized non-sliding root surfaces' if 'jaw' in n else 'inspect small bridges and holes'})
        print('EXPORTED',n,'mesh',result['stl'][mp.name]['pass'],flush=True)
    for a,label in [(30,'open'),(90,'mid'),(140,'closed')]:
        rows=m.at(a);path=ROOT/'CAD'/f'PG2_{label}.step';assembly(rows).save(str(path))
        original=cq.Compound.makeCompound([x.shape for x in rows]);result['step'][str(path.relative_to(ROOT))]=step_check(path,original)
        print('ASSEMBLY',label,result['step'][str(path.relative_to(ROOT))],flush=True)
    rows=m.at(30)+optional_parts();path=ROOT/'CAD/PG2_camera_optional.step';assembly(rows).save(str(path));result['step'][str(path.relative_to(ROOT))]=step_check(path,cq.Compound.makeCompound([x.shape for x in rows]))
    result['pass']=all(d['pass'] for d in result['stl'].values()) and all(d['pass'] for d in result['step'].values())
    result['elapsed_seconds']=time.monotonic()-start
    (ROOT/'reports/export_audit.json').write_text(json.dumps(result,indent=2));(ROOT/'reports/print_inventory.json').write_text(json.dumps(inventory,indent=2))
    (ROOT/'source/parameters_frozen.json').write_text(json.dumps(asdict(P),indent=2))
    print('PASS',result['pass'],flush=True)
    return result
if __name__=='__main__':build()
