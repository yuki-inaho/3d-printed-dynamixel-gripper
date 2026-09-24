"""Frozen acceptance contract: independent checks of metadata AND actual exported geometry.
Negative tests intentionally break the design and must be rejected, rather than updating expected values.
"""
from design import *
from dataclasses import replace
from assembly_reader import bounds
from OCP.BRepAdaptor import BRepAdaptor_Surface
import numpy as np

class RequirementViolation(ValueError):pass

def require(cond,msg):
    if not bool(cond):raise RequirementViolation(msg)

def contract(p):
    require(p.motor=='DYNAMIXEL XL430-W250','R01: motor differs from XL430-W250')
    require(tuple(p.output_axis)==(0,0,1) and tuple(p.finger_axis)==(0,0,1),'R02: output axis and finger projection must both be +Z')
    require(tuple(p.motor_long_axis)==(0,1,0),'R02: motor long dimension must remain vertical Y')
    require(p.guide_material=='printed_polymer' and p.guide_type=='rectangular_captured_slide','R04: metal/round guide substitution prohibited')
    require(p.body_side_fastener=='PHS M2.6x5 TAP','R01: wrong case side screw')
    require(p.jaw_back-p.guide_rear>0 and p.retainer_bottom-p.jaw_top>0,'R06: nominal rubbing interfaces need positive clearance')
    require(30<=p.open_angle<p.close_angle<=140,'R03: commissioned motion may not approach internal near-toggle region')
    require(p.L>p.r and p.closed_gap>=.5,'R03: invalid linkage or negative closure margin')
    return True

def geometry(m,rows=None):
    contract(m.p)
    rr=rows if rows is not None else m.at(70)
    required=['frame','retainer_top','retainer_bottom','jaw_1','jaw_-1','crank','link_1','link_-1','motor_mount']
    require(all(any(x.name==n and x.material=='printed_polymer' for x in rr) for n in required),'R03/04: printed architecture missing')
    require(sum(x.role=='actuator' for x in rr)==1,'R01: exactly one actuator')
    b=bounds(next(x.shape for x in rr if x.name=='XL430_W250'))
    require(abs((b[4]-b[1])-46.5)<.05 and abs((b[3]-b[0])-28.5)<.05,'R02: actual servo body has been laid down or substituted')
    h=next(x.shape for x in rr if x.name=='horn');axis=[]
    for f in h.Faces():
        if f.geomType()=='CYLINDER':
            a=BRepAdaptor_Surface(f.wrapped).Cylinder()
            if abs(a.Radius()-10.25)<1e-4:
                v=a.Axis().Direction();axis.append(abs(v.Z()))
    require(axis and min(axis)>.9999,'R02: actual horn axis not parallel to +Z')
    for r in rr:
        if r.material=='steel':
            require(r.role in ['fastener','servo_body_tap'],'R04: metal guide or collar added')
            bb=bounds(r.shape)
            require(max(bb[i+3]-bb[i] for i in range(3))<20.1,'R04: shaft disguised as ordinary fastener')
        if r.role=='servo_body_tap':
            tb=bounds(r.shape); side=1 if sum([tb[0],tb[3]])>0 else -1
            depth=14.25-tb[0] if side>0 else tb[3]+14.25
            require(2.5<=depth<=3.0,'R01: actual screw intrudes incorrectly into 4 mm side pilot')
        if r.material=='printed_polymer':
            require(r.shape.isValid() and len(r.shape.Solids())==1,'D06: printed component disconnected or invalid: '+r.name)
    a=next(q.shape for q in rr if q.name=='jaw_1');b=next(q.shape for q in rr if q.name=='jaw_-1')
    aa,bb=bounds(a),bounds(b)
    require(abs(aa[0]+bb[3])<1e-5 and abs(aa[3]+bb[0])<1e-5,'R03: jaw lateral symmetry broken')
    require(abs(aa[2]-4.8)<1e-5 and abs(aa[5]-36)<1e-5,'R02/03: short forward-projecting jaws replaced')
    qmap={q.name:q.shape for q in rr}
    for name in ['frame','retainer_top','retainer_bottom']:
        require(qmap['jaw_1'].distance(qmap[name])>.1499,'R06: actual guide edge/face clearance too small: '+name)
    return True

def negative_tests(m):
    trials=[]
    def reject(name,fun):
        try:fun();trials.append({'test':name,'rejected':False})
        except RequirementViolation as e:trials.append({'test':name,'rejected':True,'reason':str(e)})
    reject('wrong_XL330',lambda:contract(replace(m.p,motor='XL330-M288')))
    reject('axes_orthogonal',lambda:contract(replace(m.p,finger_axis=(0,1,0))))
    reject('metal_guide_metadata',lambda:contract(replace(m.p,guide_material='steel')))
    reject('machine_screw_in_tap_hole',lambda:contract(replace(m.p,body_side_fastener='M2.5x5')))
    reject('zero_front_guide_clearance',lambda:contract(replace(m.p,retainer_bottom=9.0)))
    reject('expanded_close_limit',lambda:contract(replace(m.p,close_angle=151)))
    rows=m.at(70)
    tipped=[replace(q,shape=q.shape.rotate((0,0,0),(1,0,0),90)) if q.name=='XL430_W250' else q for q in rows]
    reject('actual_motor_tipped_despite_good_metadata',lambda:geometry(m,tipped))
    horn=[replace(q,shape=q.shape.rotate((0,0,0),(1,0,0),90)) if q.name=='horn' else q for q in rows]
    reject('actual_horn_axis_tipped',lambda:geometry(m,horn))
    rod=Part('innocently_named_pin',cyl(3,100),(.5,.5,.5),'fixed','steel','fastener')
    reject('100mm_steel_rod_disguised_as_fastener',lambda:geometry(m,rows+[rod]))
    shifted=[replace(q,shape=q.shape.translate((.5,0,0))) if q.name=='jaw_1' else q for q in rows]
    reject('actual_jaw_not_centered',lambda:geometry(m,shifted))
    detached=cq.Compound.makeCompound([box(0,1,0,1,0,1),box(2,3,0,1,0,1)])
    fake=Part('disconnected_camera',detached,(.5,.5,.5),'camera','printed_polymer','camera_mount')
    reject('disconnected_printed_camera_stand',lambda:geometry(m,rows+[fake]))
    zero=[replace(q,shape=q.shape.translate((0,-1,0))) if q.name=='retainer_top' else q for q in rows]
    reject('actual_retainer_edge_zero_clearance_despite_good_metadata',lambda:geometry(m,zero))
    require(all(x['rejected'] for x in trials),'At least one negative test escaped the acceptance gates')
    return trials

if __name__=='__main__':
    m=Model();geometry(m)
    j={'geometry_pass':True,'negative_tests':negative_tests(m),'parameters':asdict(m.p)}
    (ROOT/'reports/guardrails.json').write_text(json.dumps(j,indent=2))
    print(json.dumps(j,indent=2))
