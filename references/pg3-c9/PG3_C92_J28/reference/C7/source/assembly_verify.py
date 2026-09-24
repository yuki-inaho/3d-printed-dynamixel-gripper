"""Stage-specific insertion and tool checks plus dimensional fastener stacks.
Rigid translations only; no claim about hand clearance, threads or actual assembly.
"""
from dataclasses import replace
import json, math, time
import numpy as np
from design import *
from check_geometry import common,bbox_overlap

def pair_fail(a,b,tol=.01):
    if not bbox_overlap(bounds(a),bounds(b)):return None
    _,v=common(a,b)
    return v if v>tol else None

def run():
    d=parts();allitems={i.name:i for i in assembled(90,d=d)}
    existing=[allitems['XL430_fixed'],allitems['XL430_horn']]
    paths=[];tools=[]
    def move(label,names):
        moving=[allitems[n] for n in names];bad=[];count=0
        for z in np.linspace(32,0,33):
            for a in moving:
                aa=a.shape.translate((0,0,float(z)))
                for b in existing:
                    v=pair_fail(aa,b.shape)
                    count+=1
                    if v:bad.append(dict(moving=a.name,blocker=b.name,offset_mm=float(z),volume_mm3=v))
        paths.append(dict(stage=label,components=names,samples=33,offset_mm=[32,0],failures=bad,pair_tests=count))
        existing.extend(moving)
        print(label,'insertion failures',len(bad),flush=True)
    def fasten(label,names):
        for n in names:
            it=allitems[n];bs=bounds(it.shape);x=(bs[0]+bs[3])/2;y=(bs[1]+bs[4])/2
            # Shaft leaves the outermost screw-head plane, not a floating tool inside the socket.
            rr=1.5 if n.startswith('case_tapper') else 1.2
            tool=cyl(rr,50,(x,y,bs[5]+.05));bad=[]
            for j in existing:
                if j.name==n:continue
                v=pair_fail(tool,j.shape)
                if v:bad.append(dict(blocker=j.name,volume_mm3=v))
            tools.append(dict(stage=label,screw=n,diameter_mm=2*rr,length_mm=50,failures=bad))
            existing.append(it)
    move('S1_frame',['frame']+[n for n in allitems if n.startswith('cap_') and n.endswith('_nut')])
    fasten('S1_case_mount',[n for n in allitems if n.startswith('case_tapper')])
    move('S2_drive',['horn_spacer','crank','pivot_drive_R_nut','pivot_drive_L_nut'])
    fasten('S2_horn',[f'horn_bolt_{j}' for j in range(4)])
    for lr in ['R','L']:
        move('S3_bare_carriage_'+lr,['carriage_'+lr,'pivot_carriage_'+lr+'_nut']+[n for n in allitems if n.startswith('finger_'+lr+'_') and n.endswith('_nut')])
    for lr in ['R','L']:
        move('S4_link_'+lr,['link_'+lr])
    # Washers are loaded over the bolt before insertion. A point seating contact is intended.
    for n in allitems:
        if n.startswith('pivot_') and n.endswith('_washer'):existing.append(allitems[n])
    fasten('S4_pivots',[n for n in allitems if n.startswith('pivot_') and n.endswith('_bolt')])
    move('S5_caps',['cap_U','cap_D'])
    existing += [allitems[n] for n in allitems if n.startswith('cap_') and n.endswith('_washer')]
    fasten('S5_caps',[n for n in allitems if n.startswith('cap_') and n.endswith('_bolt')])
    for lr in ['R','L']:move('S6_finger_'+lr,['finger_'+lr])
    existing += [allitems[n] for n in allitems if n.startswith('finger_') and n.endswith('_washer')]
    fasten('S6_fingers',[n for n in allitems if n.startswith('finger_') and n.endswith('_bolt')])
    rows=[]
    for label,count,L,seat,nut_z,nut_h,stop in [
        ('drive_pivot',2,10,30.3,20.7,1.6,None),
        ('carriage_pivot',2,8,30.3,23.05,1.6,None),
        ('cap',4,12,27.4,17.2,1.6,None),
        ('finger',4,16,P.finger_mount_z+3.3,P.finger_nut_z,1.6,None),
        ('horn',4,6,22.5,15.5,3.5,15.5),
        ('case_self_tapper',2,5,19.35,13,4,13)]:
        tip=seat-L;eng=max(0,min(seat,nut_z+nut_h)-max(tip,nut_z))
        row=dict(name=label,count=count,length_mm=L,seat_z=seat,tip_z=tip,engagement_nominal_mm=eng,
            bottom_clearance_mm=tip-stop if stop is not None else None,
            protrusion_below_nut_mm=max(0,nut_z-tip) if stop is None else None)
        row['pass']=eng>= (1.59 if stop is None else 2.0) and (stop is None or tip-stop>=.5)
        rows.append(row)
    # Independent analytic face areas. Annular washer sits on printed shoulder, NOT rotating link.
    bearing_area=math.pi*((5/2)**2-(2.3/2)**2)
    stack={'pivot_radial_gap_per_side_mm':(P.link_bore-P.shoulder_d)/2,
           'pivot_axial_total_gap_mm':P.shoulder_top-P.shoulder_base-P.link_thickness,
           'pivot_nominal_front_back_gap_mm':[.3,.3],
           'printed_shoulder_bearing_area_mm2':bearing_area,
           'guide_depth_total_gap_mm':24.1-19.5-(23.8-19.8),
           'guide_outer_side_gap_mm':22-21.7,
           'link_tip_to_finger_surface_gap_mm':P.finger_start-29.5,
           'pivot_retainer_OD_mm':7.0,'pivot_retainer_ID_mm':2.2,'pivot_retainer_t_mm':.5,'pivot_retaining_radial_overlap_mm':(7-P.link_bore)/2,'no_physical_test':True}
    ok=not any(x['failures'] for x in paths+tools) and all(x['pass'] for x in rows) and stack['pivot_retaining_radial_overlap_mm'] >= .5
    out=dict(revision=P.revision,pass_=ok,insertion_paths=paths,tool_access=tools,fastener_stacks=rows,fit_stack=stack,
        assembly_angle_deg=90,limitations=['No tool handle or human hand volume checked','Insertion paths sampled at 1 mm, not a continuous proof','Bolt/hole threads represented as cylinders; actual screw and pilot must be verified','Screw-head diameter <=3.8 mm, height <=2 mm required; general washers ID2.2 OD5 thickness0.3 mm; FOUR pivot retainers ID2.2 OD7 thickness0.5 mm'])
    (ROOT/'reports/assembly.json').write_text(json.dumps(out,indent=2,ensure_ascii=False));print('RESULT',ok,flush=True)
    if not ok:raise SystemExit(2)
if __name__=='__main__':run()
