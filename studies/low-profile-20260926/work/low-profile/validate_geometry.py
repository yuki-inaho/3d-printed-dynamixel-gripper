"""Saved CAD collision changes and sampled wrist travel, preserving unknowns."""
import hashlib
import json
from collections import Counter
from itertools import combinations

import numpy as np

from compare import candidate_spec
from design import REPO
from study import OUT, ROOT, save
from gripper_design.camera_overhead_r4 import retained_at
from scripts.assembly_io import bounds, read_step
from scripts.id4_sweep_d405_r5 import MOVING, id4_axis
from scripts.validate_camera_overhead_d405_r5 import external_pair, internal_pair
from scripts.validate_camera_overhead_r4 import box_distance, pair

CHANGED = {'PG3_finger_L','PG3_finger_R','PG3_pad_L','PG3_pad_R'}


def scan(parts, spec, angle):
    arm = retained_at({n:s for n,s in parts.items() if not n.startswith('CAM5_')},angle)
    camera = {n:s for n,s in parts.items() if n.startswith('CAM5_')}
    scene = arm | camera
    bbs = {n:bounds(s) for n,s in scene.items()}
    rows=[]
    tested=0
    for a,b in combinations(scene,2):
        if a not in CHANGED and b not in CHANGED and a not in camera and b not in camera:
            continue
        tested+=1
        if box_distance(bbs[a],bbs[b])>=.3:
            continue
        if a in camera and b in camera:
            result=internal_pair(a,scene[a],b,scene[b],spec)
        elif a in camera or b in camera:
            ca,other=(a,b) if a in camera else (b,a)
            result=external_pair(ca,scene[ca],other,scene[other])
        else:
            # Actual same-side pad/finger mating and root interfaces are assessed as contact;
            # positive material intersection still fails in pair().
            contact = any({a,b}=={f'PG3_finger_{side}',f'PG3_pad_{side}'} or
                          {a,b}=={f'PG3_finger_{side}',f'PG3_carriage_{side}'} for side in ['L','R'])
            result=pair(scene[a],scene[b],contact=contact)
        if result['status']!='PASS':
            rows.append({'a':a,'b':b,**result})
    return {'angle':angle,'pair_count':tested,'nonpass':rows}


def newly_worse(old,new):
    previous={(r['a'],r['b'],r['status']):r for r in old}
    out=[]
    for row in new:
        key=(row['a'],row['b'],row['status'])
        prior=previous.get(key)
        if prior is None:
            out.append(row|{'change':'new'})
        elif row.get('intersection_mm3',0)>prior.get('intersection_mm3',0)+1e-5:
            out.append(row|{'change':'increased_material_overlap','previous_mm3':prior.get('intersection_mm3',0)})
        elif 'gap_mm' in row and 'gap_mm' in prior and row['gap_mm'] < prior['gap_mm']-1e-5:
            out.append(row|{'change':'decreased_existing_gap','previous_gap_mm':prior['gap_mm']})
    return out


def wrist_hit(group,upstream,point,axis,angle):
    ub={n:bounds(s) for n,s in upstream.items()}
    for n,s in group.items():
        moved=s.rotate(tuple(point),tuple(point+axis),angle) if angle else s
        bb=bounds(moved)
        for m,t in upstream.items():
            if box_distance(bb,ub[m])>=.3:
                continue
            result=pair(moved,t)
            if result['status']!='PASS':
                return {'moving':n,'upstream':m,**result}
    return None


def wrist(parts):
    upstream={n:s for n,s in parts.items() if not n.startswith(MOVING)}
    point,axis,_=id4_axis(parts)
    mount={n:s for n,s in parts.items() if n.startswith('CAM5_')}
    arm={n:s for n,s in parts.items() if not n.startswith('CAM5_')}
    result={'axis_point_mm':point.tolist(),'axis_direction':axis.tolist(),'step_deg':2,'continuous_proof':False,'cases':[]}
    for jaw in [25.,90.,135.]:
        dynamic=retained_at(arm,jaw)
        group=mount|{n:dynamic[n] for n in CHANGED}
        row={'gripper_angle_deg':jaw,'zero':wrist_hit(group,upstream,point,axis,0),'limits':[],'stops':[]}
        for sign in [-1,1]:
            last=0
            stop=None
            for deg in range(sign*2,sign*182,sign*2):
                hit=wrist_hit(group,upstream,point,axis,deg)
                if hit:
                    stop={'angle_deg':deg,'first_hit':hit}
                    break
                last=deg
            row['limits'].append(last)
            row['stops'].append(stop)
        result['cases'].append(row)
        print('wrist',jaw,row['limits'],flush=True)
    inherited=json.loads((REPO/'outputs/camera-mount-id5-overhead-d405-r5/reports/id4_sweep.json').read_text())
    result['unchanged_arm_reference']=inherited['arm_only']
    result['physical_limits_deg']=[max(inherited['arm_only']['free_interval_deg'][0],*(r['limits'][0] for r in result['cases'])),
                                   min(inherited['arm_only']['free_interval_deg'][1],*(r['limits'][1] for r in result['cases']))]
    result['onshape_urdf_limits_deg']=[-result['physical_limits_deg'][1],-result['physical_limits_deg'][0]]
    return result


def main():
    from dataclasses import replace
    from gripper_design.camera_overhead_d405_r5 import Spec
    path=OUT/'CAD/Robot_250g_low_profile_D405.step'
    parts={r.name:r.world for r in read_step(path)[2]}
    old={r.name:r.world for r in read_step(ROOT/'outputs/optimization-250g/CAD/Robot_250g_compact_D405.step')[2]}
    spec=candidate_spec(json.loads((OUT/'reports/selection.json').read_text()))
    oldspec=replace(Spec(),glass_center=(-.2,185,250),pitch_deg=75)
    report={'cad_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'gripper_step_deg':5,'cases':[],
            'scope':'all changed parts and camera versus all retained parts; unchanged/unchanged pairs inherit source evidence',
            'physical_installation_approved':False}
    for angle in range(25,136,5):
        baseline=scan(old,oldspec,angle)
        candidate=scan(parts,spec,angle)
        record={'angle':angle,'baseline':baseline,'candidate':candidate,'new_or_worsened':newly_worse(baseline['nonpass'],candidate['nonpass'])}
        report['cases'].append(record)
        save('geometry-validation.json',report)
        print('gripper',angle,'old',dict(Counter(r['status'] for r in baseline['nonpass'])),'new',dict(Counter(r['status'] for r in candidate['nonpass'])),'worsened',len(record['new_or_worsened']),flush=True)
    report['wrist']=wrist(parts)
    report['no_new_or_worsened_gripper_defects']=all(not r['new_or_worsened'] for r in report['cases'])
    report['zero_wrist_clear']=all(r['zero'] is None for r in report['wrist']['cases'])
    save('geometry-validation.json',report)
    print('VALIDATION',report['no_new_or_worsened_gripper_defects'],report['wrist']['physical_limits_deg'],flush=True)


if __name__=='__main__':
    main()
