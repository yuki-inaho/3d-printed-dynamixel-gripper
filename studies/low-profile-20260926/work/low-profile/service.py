"""Explicitly assumed straight tool envelopes in named assembly stages."""
import hashlib
import json

import cadquery as cq
import numpy as np

from compare import candidate_spec
from study import OUT, save
from gripper_design import camera_overhead_d405_r5 as r5
from gripper_design.camera_overhead_r4 import ANCHORS, TOP, screw_stack
from scripts.assembly_io import bounds, read_step
from scripts.validate_camera_overhead_r4 import box_distance, pair


def tool(head, axis, withdrawal=100):
    head,axis=np.array(head),np.array(axis)
    shapes=[]
    for radius,offset,length in [(1.5,.05,75),(10,75.05,30),(40,70.05,100)]:
        shapes.append(cq.Solid.makeCylinder(radius,length+withdrawal,cq.Vector(*(head+offset*axis)),cq.Vector(*axis)))
    return shapes[0].fuse(*shapes[1:])


def inspect(envelope,parts,target):
    hits=[]
    bb=bounds(envelope)
    for name,shape in parts.items():
        gap=.01 if name==target else .3
        if box_distance(bb,bounds(shape))>=gap:
            continue
        result=pair(envelope,shape,min_gap=gap)
        if result['status']!='PASS':
            hits.append({'part':name,**result})
    return hits


def main():
    path=OUT/'CAD/Robot_250g_low_profile_D405.step'
    parts={r.name:r.world for r in read_step(path)[2]}
    spec=candidate_spec(json.loads((OUT/'reports/selection.json').read_text()))
    norm=r5.basis(spec.pitch_deg)[2]
    tests=[]
    for i,(x,y,z) in enumerate(ANCHORS):
        tests.append((f'CAM5_BASE_TAP_{i}',(x,y,TOP+spec.base_seat_thickness+.5+2),(0,0,1),'base_before_carrier'))
    for i,x in enumerate([-10,10]):
        tests.append((f'CAM5_D405_SCREW_{i}',r5.local_point((x,0,spec.plate_thickness-spec.d405_counterbore_depth+3),spec),norm,'camera_carrier_bench'))
    for i,x in enumerate([-spec.tie_bolt_local[0],spec.tie_bolt_local[0]]):
        tests.append((f'CAM5_TIE_BOLT_{i}',r5.local_point((x,spec.tie_bolt_local[1],spec.plate_thickness+.5+3),spec),norm,'final_installed'))
    for side in ['L','R']:
        for suffix in ['-14','14']:
            name=f'PG3_finger_{side}_{suffix}_bolt'
            b=bounds(parts[name])
            tests.append((name,((b[0]+b[3])/2,b[4],(b[2]+b[5])/2),(0,1,0),'fingers_before_camera'))
    report={'cad_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'assumed_envelope':{'shaft_radius_mm':1.5,'shaft_length_mm':75,'handle_radius_mm':10,'handle_length_mm':30,
                                'hand_radius_mm':40,'hand_length_mm':100,'positive_axis_withdrawal_mm':100},
            'scope':'continuous straight withdrawal envelope plus axial rotation; starts 0.05 mm above head, no bit engagement proof',
            'tools_measured':False,'physical_assembly_approved':False,'checks':[],
            'base_stack':screw_stack(spec.base_screw_length,spec.base_seat_thickness,.5,spec.hole_depth),
            'd405_stack':r5.d405_stack(spec)}
    for target,head,axis,stage in tests:
        envelope=tool(head,axis)
        installed=inspect(envelope,parts,target)
        if stage=='base_before_carrier':
            present={n:s for n,s in parts.items() if not n.startswith('CAM5_') or n=='CAM5_BASE' or n.startswith(('CAM5_BASE_TAP_','CAM5_BASE_WASHER_'))}
        elif stage=='camera_carrier_bench':
            present={n:s for n,s in parts.items() if n.startswith('CAM5_D405_')}
        elif stage=='fingers_before_camera':
            present={n:s for n,s in parts.items() if not n.startswith('CAM5_')}
        else:
            present=parts
        staged=inspect(envelope,present,target)
        report['checks'].append({'target':target,'head_mm':list(head),'axis':list(axis),'stage':stage,
                                'present':sorted(present),'absent_at_stage':sorted(set(parts)-set(present)),
                                'installed_nonpass':installed,'stage_nonpass':staged,'stage_envelope_pass':not staged})
        save('service-validation.json',report)
        print('tool',target,stage,'installed',len(installed),'stage',len(staged),flush=True)
    report['all_staged_envelopes_pass']=all(r['stage_envelope_pass'] for r in report['checks'])
    report['limitations']=['Actual tool socket fit and tightening torque unknown','Nut loading/retention and cluster insertion are separate from above-head access',
                           'Free cable routing beyond nominal plug and stub unverified','Full physical fastening/printing acceptance remains open']
    save('service-validation.json',report)


if __name__=='__main__':
    main()
