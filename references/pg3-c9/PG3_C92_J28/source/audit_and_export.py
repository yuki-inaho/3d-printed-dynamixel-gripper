"""Recheck the C92-J28 variant against frozen geometry and changed interfaces.
Usage: python audit_and_export.py --stage sanity|sweep|assembly|export|saved|audit
Reports record actual execution. No old report is re-labeled as a new pass.
"""
from __future__ import annotations
import argparse, json, time, math, hashlib, sys
from pathlib import Path
from dataclasses import asdict
from itertools import combinations
import numpy as np
import jaw_revision as j
from jaw_revision import base, P, ROOT
from check_geometry import collision_check, common, bbox_overlap
from shape_signature import compare
from pose import pose
from printing import print_orientation


def write(name, data):
    data = {'revision': j.REVISION, 'source_sha256':hashlib.sha256((ROOT/'source/jaw_revision.py').read_bytes()).hexdigest(), **data}
    (ROOT/'reports'/name).write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return data


def sanity():
    d = j.parts(); records=[]; cache=set()
    for a in [25,55,90,115,135]:
        r=collision_check(j.assembled(a,d=d),rigid_cache=cache)
        records.append({'angle':a,**r})
        print(a,r['failures'],flush=True)
    out=write('sanity.json',{'pass':all(not r['failures'] for r in records),'records':records})
    return out['pass']


_REF=None
_CACHE=None

def _init_worker():
    global _REF, _CACHE
    _REF=j.assembled(90,d=j.parts());_CACHE=set()


def _angles(chunk):
    records=[];distances=[]
    # Static seating is verified separately. Different-body fits are not excluded from collision tests.
    changed={'finger_R','finger_L','carriage_R','carriage_L','pad_R','pad_L'}
    fit_pairs={tuple(sorted((f'carriage_{lr}',n))) for lr in ['R','L'] for n in ['frame','cap_U','cap_D',f'link_{lr}']}
    for angle in chunk:
        items=pose(_REF,angle);r=collision_check(items,rigid_cache=_CACHE)
        records.append({'angle_deg':angle,**r})
        if abs(angle/2.5-round(angle/2.5)) < 1e-8:
            for a,b in combinations(items,2):
                if a.name not in changed and b.name not in changed:continue
                if a.group==b.group:continue
                key=tuple(sorted((a.name,b.name)))
                # Distance of axis-aligned boxes gives a conservative lower bound.
                ba,bb=base.bounds(a.shape),base.bounds(b.shape)
                lb=math.sqrt(sum(max(0,ba[k]-bb[k+3],bb[k]-ba[k+3])**2 for k in range(3)))
                if lb>=.8:continue
                distance=float(a.shape.distance(b.shape))
                distances.append({'pair':key,'angle':angle,'distance_mm':distance,'designated_fit':key in fit_pairs})
    return records, distances


def sweep():
    from concurrent.futures import ProcessPoolExecutor
    t=time.monotonic();angles=[float(a) for a in np.linspace(25,135,221)]
    chunks=[angles[k:k+13] for k in range(0,len(angles),13)]; records=[];distances=[]
    with ProcessPoolExecutor(max_workers=4,initializer=_init_worker) as pool:
        for index,(rs,ds) in enumerate(pool.map(_angles,chunks)):
            records.extend(rs);distances.extend(ds)
            print('sweep',len(records),'/221','failures',sum(len(r['failures']) for r in records),flush=True)
    bad=[{'angle':r['angle_deg'],**f} for r in records for f in r['failures']]
    too_close=[d for d in distances if not d['designated_fit'] and d['distance_mm']<.29999]
    out=write('motion.json',{'pass':not bad and not too_close,'sample_count':221,'step_deg':.5,
        'threshold_mm3':.01,'failures':bad,'nonfit_distance_failures':too_close,
        'distance_sampling_deg':2.5,'distance_records':distances,'records':records,
        'elapsed_s':time.monotonic()-t,
        'scope':'All assembly body collision tests; distance checks focus on changed parts. Discrete nominal rigid geometry, not continuous or physical certification.'})
    return out['pass']


def assembly():
    # Inject the revised geometry and report destination into the unmodified C7
    # stage-specific insertion/tool routine. Its checks and thresholds are unchanged.
    import assembly_verify as routine
    routine.parts=j.parts;routine.assembled=j.assembled;routine.P=P;routine.ROOT=ROOT
    routine.run()
    data=json.loads((ROOT/'reports/assembly.json').read_text())
    write('assembly.json',data)
    return data['pass_']


def export():
    d=j.parts();out={'parts':[],'assemblies':[],'parameters':asdict(P),'units':'mm'}
    for name,shape in d.items():
        folder='changed_parts' if name in j.CHANGED_PARTS else 'unchanged_C7'
        (ROOT/'STL'/folder).mkdir(parents=True,exist_ok=True)
        pp=print_orientation(name,shape)
        stl=f'STL/{folder}/{name}.stl';step=f'CAD/parts/{name}.step'
        base.cq.exporters.export(pp,str(ROOT/stl),tolerance=.035,angularTolerance=.08)
        base.cq.exporters.export(shape,str(ROOT/step))
        out['parts'].append({'name':name,'changed':name in j.CHANGED_PARTS,'count':base.PRINT_COUNTS[name],
                            'stl':stl,'step':step,'volume_mm3':shape.Volume(),'print_bounds':base.bounds(pp)})
    for a,label in [(25,'open'),(90,'mid'),(135,'closed')]:
        its=j.assembled(a,d=d,world_coords=True);assembly=base.cq.Assembly(name='C92_J28_'+label)
        for item in its:assembly.add(item.shape,name=item.name,color=base.cq.Color(*item.color))
        fn=f'CAD/C92_J28_{label}.step';assembly.save(str(ROOT/fn))
        out['assemblies'].append({'file':fn,'angle':a,'count':len(its),'items':[{'name':i.name,'volume_mm3':i.shape.Volume()} for i in its]})
    write('export_manifest.json',out);return True


def saved():
    import trimesh
    from assembly_reader import read_step
    manifest=json.loads((ROOT/'reports/export_manifest.json').read_text());d=j.parts();checks=[];asms=[]
    for row in manifest['parts']:
        mesh=trimesh.load(ROOT/row['stl'],force='mesh',process=True)
        st=base.cq.importers.importStep(str(ROOT/row['step'])).val()
        vr=abs(mesh.volume-row['volume_mm3'])/row['volume_mm3']
        cmp=compare(st,d[row['name']],tol=1e-5)
        ok=bool(mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0 and len(mesh.split())==1 and vr<.002 and cmp['pass_'])
        checks.append({'name':row['name'],'pass':ok,'closed':bool(mesh.is_watertight),'relative_volume_error':float(vr),'step_compare':cmp})
    for row in manifest['assemblies']:
        _,_,saved_rows=read_step(ROOT/row['file']); expected={i.name:i for i in j.assembled(row['angle'],d=d,world_coords=True)}
        names=[r.name for r in saved_rows];errs=[];items=[]
        for r in saved_rows:
            if r.name not in expected:
                errs.append('unknown name '+r.name);continue
            cmp=compare(r.world,expected[r.name].shape,tol=1e-5)
            if not cmp['pass_']:errs.append({'name':r.name,'comparison':cmp})
            it=expected[r.name]
            # Collision checker is in construction coordinates, including its named thread zone.
            construction=r.world.rotate((0,0,0),(1,0,0),-90)
            items.append(base.Item(r.name,construction,it.group,it.kind,it.color))
        collisions=collision_check(items)
        ok=len(names)==len(expected) and set(names)==set(expected) and not errs and not collisions['failures']
        asms.append({'file':row['file'],'pass':ok,'count':len(names),'errors':errs,'collision_result':collisions})
        print('saved',row['file'],ok,flush=True)
    result=write('saved.json',{'pass':all(c['pass'] for c in checks+asms),'parts':checks,'assemblies':asms})
    return result['pass']


def audit():
    from scipy.optimize import brentq
    d=j.parts();old=base.parts();checks=j.independent_jaw_requirements(d)
    frozen=[]
    for name in d:
        if name in j.CHANGED_PARTS:continue
        frozen.append({'name':name,**compare(old[name],d[name])})
    olditems={i.name:i for i in base.assembled(90,d=old)};newitems={i.name:i for i in j.assembled(90,d=d)}
    for name,it in olditems.items():
        if name.startswith(('carriage_','finger_','pad_')) and it.kind!='fastener':continue
        frozen.append({'name':'assembly/'+name,**compare(it.shape,newitems[name].shape)})
    samples=[]
    for a in np.linspace(25,135,1101):
        t=math.radians(a);x=base.pos(a,P)
        samples.append(abs(math.hypot(x-P.r*math.cos(t),P.r*math.sin(t))-P.L))
    object_tests=[]
    # Flat boxes plus a cylinder. Tests check contact and free forward approach;
    # they do not assert stable grasp, friction, or load capacity.
    for width in [10.,25.,45.]:
        angle=brentq(lambda a:base.opening(a,P)-width,25,135)
        items=j.assembled(angle,d=d)
        for typ in ['box']+(['cylinder'] if width==25 else []):
            obj=(base.box(-width/2,width/2,-12,12,39.7,59.7) if typ=='box'
                 else base.cyl(width/2,24,(0,-12,52.2),d=(0,1,0)))
            bad=[]
            for travel in [0,5,10,20,30]:
                shape=obj.translate((0,0,travel))
                for it in items:
                    if not bbox_overlap(base.bounds(shape),base.bounds(it.shape)):continue
                    _,v=common(shape,it.shape)
                    if v>.01:bad.append({'component':it.name,'advance_mm':travel,'volume_mm3':v})
            pad_dist={it.name:float(obj.distance(it.shape)) for it in items if it.kind=='pad'}
            object_tests.append({'width_mm':width,'shape':typ,'angle_deg':angle,'failures':bad,
                                 'pad_distance_mm':pad_dist,'pass':not bad and max(pad_dist.values())<1e-5})
    # Mutation tests run actual shape predicates, not a configured boolean list.
    mutants=[]
    def reject(label,replaced):
        r=j.independent_jaw_requirements(replaced)
        mutants.append({'mutation':label,'rejected':not r['pass'],'failed_checks':[k for k,v in r['checks'].items() if not v]})
    reject('old shallow C7 fingers',{**d,'05_finger_R':old['05_finger_R'],'06_finger_L':old['06_finger_L']})
    damaged=base.cut(d['05_finger_R'],base.box(-10.6,-5.4,-8,8,45,50))
    reject('window through backing beneath pad',{**d,'05_finger_R':damaged})
    reject('original short bearing shoes',{**d,'03_carriage_R':old['03_carriage_R'],'04_carriage_L':old['04_carriage_L']})
    wide=base.fuse(d['01_frame'],base.box(45,48,-4,4,17,19.5))
    reject('oversized fixed frame',{**d,'01_frame':wide})
    too_long=base.fuse(d['03_carriage_R'],base.box(-14,-10.8,18,21.7,19.8,23.8))
    reject('shoes collide at closed endpoint',{**d,'03_carriage_R':too_long,'04_carriage_L':base.mirror(too_long)})
    unsafe_shoe=base.fuse(d['03_carriage_R'],base.box(-11,-6.8,18,18.6,19.8,23.8),base.box(-11,-6.8,-18.6,-18,19.8,23.8))
    reject('C8 inboard-shoe insufficient crank clearance', {**d, '03_carriage_R':unsafe_shoe,'04_carriage_L':base.mirror(unsafe_shoe)})
    # Force illustration: assumed independent test force and Coulomb coefficients.
    guide_plane=21.8;force=5.;cent_old=base.P.finger_end-1.5;cent_new=P.finger_end-1-20/2
    loads=[]
    for label,z,b_length in [('C7 pad center',cent_old,12.),('J28 pad center',cent_new,16.),('J28 pad front edge',59.7,16.)]:
        e=z-guide_plane;moment=force*e;reaction=moment/b_length
        loads.append({'case':label,'assumed_force_each_N':force,'force_plane_z_mm':z,'guide_plane_z_mm':guide_plane,
                      'lever_mm':e,'moment_Nmm':moment,'assumed_effective_contact_separation_mm':b_length,
                      'pure_couple_reaction_each_N':reaction,
                      'illustrative_total_moment_friction_N':{str(mu):2*mu*reaction for mu in [.1,.2,.3]}})
    # Intentionally simplistic unsupported-front-plate beam, no material pass/fail.
    span=59.7-36.;breadth=36.;thickness=5.;I=breadth*thickness**3/12
    stress=force*span*(thickness/2)/I
    # Mounting bolt group also sees the carried moment. Axial force estimate at
    # the outer mounting line and a 3-mm lug requires a measured/contact FEA model.
    root_arm_projection=6.3-(-5.5);root_moment=force*(59.7-33.)
    bolts_total_axial=root_moment/root_arm_projection
    load_report={'assumptions':'5 N per jaw is a test candidate, NOT a rating. Effective reaction separations 12/16 mm and mu .1/.2/.3 are assumptions, not measured tribology. Couple/friction estimates omit link-angle side force, uneven sharing, compliance and wear.',
                 'illustrations':loads,'front_plate_beam':{'unsupported_length_mm':span,'I_mm4':I,'nominal_stress_MPa':stress,
                 'at_assumed_E_1000_MPa_deflection_mm':force*span**3/(3*1000*I),
                 'scope':'Ideal 5x36 mm rectangular beam from mount-front z36, no stress concentrations, layers or lug compliance. NOT a structural qualification.'},
                 'mounting_group_rough_check':{'moment_Nmm':root_moment,'assumed_force_couple_arm_mm':root_arm_projection,'estimated_axial_group_force_N':bolts_total_axial,
                    'limitations':'Approximate statics only; printed lugs, clamping, prying, nut capture and fasteners need physical checking.'},
                 'physical_strength_pass':None,'friction_pass':None,'physical_tests_performed':[]}
    write('load_review.json',load_report)
    ok=checks['pass'] and all(c['pass_'] for c in frozen) and max(samples)<1e-8 and all(r['pass'] for r in object_tests) and all(m['rejected'] for m in mutants)
    result=write('requirements.json',{'pass':ok,'jaw_requirements':checks,'frozen_components':frozen,
        'kinematic_checks':{'samples':1101,'max_link_constraint_error_mm':max(samples)},'grasp_space_tests':object_tests,'negative_tests':mutants,
        'part_volume_comparison_mm3':{name:{'old':old[name].Volume(),'new':d[name].Volume()} for name in j.CHANGED_PARTS}})
    print('AUDIT',ok,flush=True)
    return ok


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--stage',required=True,choices=['sanity','sweep','assembly','export','saved','audit']);args=ap.parse_args()
    if not globals()[args.stage]():raise SystemExit(2)
