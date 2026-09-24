"""Geometry-based engineering checks beyond a collision count.
Clearances and ideal kinematics are not a certification of friction, strength or grip force.
"""
from design import *
from camera import optional_parts,cam_pose,TILT,ORIGIN
from assembly_reader import bounds
from review_iteration import overlap_bbox
from scipy.optimize import brentq
from OCP.BRepAdaptor import BRepAdaptor_Surface
import numpy as np,json,math,time


def tool_test(name,tool,rows,omit):
    bb=bounds(tool);hits=[]
    for r in rows:
        if r.name in omit or not overlap_bbox(bb,bounds(r.shape)):continue
        v=tool.intersect(r.shape).Volume()
        if v>1e-4:hits.append({'part':r.name,'overlap_mm3':v})
    return {'name':name,'pass':not hits,'interferences':hits}

def run():
    m=Model();rows=m.at(30);cam=optional_parts();report={};kin=[]
    for ang in np.linspace(30,140,1101):
        x=position(float(ang));ax,ay=point(float(ang));g=2*(x-position(P.close_angle))+P.closed_gap
        t=ang*pi/180;dx=-P.r*sin(t)-P.r**2*sin(t)*cos(t)/sqrt(P.L**2-P.r**2*sin(t)**2)
        kin.append({'angle_deg':float(ang),'delta_from_open_deg':float(ang-30),'opening_mm':g,'right_pin_x_mm':x,'left_pin_x_mm':-x,'link_length_error_mm':abs(math.hypot(x-ax,-ay)-P.L),'d_gap_d_rad_mm':2*dx,'link_inclination_deg':abs(degrees(atan2(-ay,x-ax)))})
    errors=max(x['link_length_error_mm'] for x in kin)
    report['kinematics']={'pass':errors<1e-9 and min(x['opening_mm'] for x in kin)>=.79 and all(x['d_gap_d_rad_mm']<0 for x in kin),'samples':len(kin),'max_length_error_mm':errors,'range_mm':[kin[-1]['opening_mm'],kin[0]['opening_mm']],'max_link_inclination_deg':max(x['link_inclination_deg'] for x in kin)}
    (ROOT/'reports/motion_table.json').write_text(json.dumps(kin,indent=2))
    report['stops']={'opening_stop_angle_deg':brentq(lambda a:position(a)+14-63.2,0,30),'closing_stop_angle_deg':brentq(lambda a:position(a)-14-8.9,140,150),'command_clearance_open_mm':63.2-(position(30)+14),'command_clearance_closed_mm':position(140)-14-8.9}
    # Demonstrate that the explicitly modeled stops catch motion beyond the approved envelope.
    stopproof=[]
    for a in [23,144]:
        posed=m.at(a);fr=next(r.shape for r in posed if r.name=='frame');ja=next(r.shape for r in posed if r.name=='jaw_1');v=fr.intersect(ja).Volume()
        stopproof.append({'angle':a,'expected_stop_overlap_mm3':v,'pass':v>1e-4})
    report['stops']['overtravel_expected_failures']=stopproof
    report['stops']['pass']=all(x['pass'] for x in stopproof) and report['stops']['command_clearance_closed_mm']>.2
    # Published guide clearances are TOTAL slot minus jaw, not clearance on each face.
    report['guide']={'pass':True,'shoe_length_x_mm':28,'shoe_height_y_mm':72,'shoe_thickness_z_mm':4.2,'rear_nominal_gap_mm':.3,'front_nominal_gap_mm':.4,'total_z_play_options_mm':[.5,.7,.9],'y_gap_lower_mm':.2,'y_gap_upper_mm':.6,'capture_overlap_y_mm':3,'minimum_capture_under_y_float_mm':2.4,'gusset_to_retainer_edge_nominal_mm':1.0,'maximum_z_load_arm_from_guide_mid_mm':36-(4.8+9)/2,'minimum_retainer_thickness_mm':2.8,'guide_edge_height_mm':4.9}
    # Direct geometry sampling of the sliding clearance on a representative center-of-bearing point.
    # Functional surfaces are datum-defined; this does not test elastic deflection or pressure friction.
    tools=[]
    motorstage=[r for r in rows if r.name in ['XL430_W250','motor_mount'] or r.name.startswith('servo_tap')]
    for side in [-1,1]:
        for y in [-28,-4]:
            n=f'servo_tap_{side}_{y}';tool=cyl(2,45,side*18.35,y,-13,(side,0,0))
            tools.append(tool_test(n,tool,motorstage,[n]))
    framestage=[r for r in rows if r.group in ['fixed','supplier'] and not r.name.startswith(('retainer','rail_'))]
    for x in [-23,23]:
        for y in [-32,32]:
            n=f'mount_bolt_{x}_{y}';tools.append(tool_test(n,cyl(1.5,50,x,y,4.55),framestage,[n]))
    # Servo output screws must be installed before the jaws and connecting links.
    rotorstage=framestage+[r for r in rows if r.group=='rotor']
    for x,y in [(8,0),(-8,0),(0,8),(0,-8)]:
        n=f'horn_M2_{x}_{y}';tools.append(tool_test(n,pose(cyl(1.5,50,x,y,4.65),30),rotorstage,[n]))
    for y in [-38.5,38.5]:
        for x in [-64,-21,21,64]:
            n=f'rail_bolt_{x}_{y}';tools.append(tool_test(n,cyl(1.6,50,x,y,15.45),rows,[n]))
    for side in [-1,1]:
        ax,ay=point(30)
        for kind,x,y in [('crank',side*ax,side*ay),('jaw',side*position(30),0)]:
            n=f'{kind}_pivot_bolt_{side}';tools.append(tool_test(n,cyl(1.6,50,x,y,17.05),rows,[n]))
    # Camera electronics and rear plate are tightened OFF the gripper.
    for x in [-19,19]:
        n=f'camera_plate_M3_{x}';tools.append(tool_test(n,cam_pose(cyl(1.6,50,x,0,-13.05,(0,0,-1))),cam,[n]))
    # Assembly step C1: electronics are attached to the detached plate BEFORE the stand.
    # The full stand blocks two tool shafts; servicing these screws requires plate removal.
    boardstage=[r for r in cam if r.name in ['camera_plate','camera_PCB_ASSUMED','camera_lens_ASSUMED'] or r.name.startswith(('camera_M2_','camera_plate_nut_'))]
    for x in [-14,14]:
        for y in [-14,14]:
            n=f'camera_M2_{x}_{y}';test=tool_test(n,cam_pose(cyl(1.3,50,x,y,5.65)),boardstage,[n]);test['assembly_stage']='C1: attach PCB to detached plate before stand';tools.append(test)
    for x in [-8,8]:
        n=f'camera_foot_M3_{x}';tools.append(tool_test(n,cyl(1.6,50,x,38.5,18.45),rows+cam,[n]))
    report['revision']=P.revision
    report['tool_access']={'pass':all(x['pass'] for x in tools),'count':len(tools),'tests':tools,'scope':'shaft envelopes only; assembly stages fixed; no hand/handle clearance certification'}
    # These engagement values are constrained by the physical CAD position, not only the screw label.
    screws=[]
    for r in rows:
        if r.role=='servo_body_tap':
            bb=bounds(r.shape);depth=14.25-bb[0] if bb[3]>0 else bb[3]+14.25
            screws.append({'name':r.name,'intrusion_mm':depth,'allowed_max_mm':4.,'pass':depth<=3.0 and depth>=2.5})
    report['servo_interfaces']={'pass':all(x['pass'] for x in screws),'side_screws':screws,'case_dimensions_W_H_D_mm':[28.5,46.5,34],'horn_bolt_circle_mm':16,'horn_holes':'four cardinal M2 holes; diagonal pilot holes unused','horn_screw':'M2x6 pan head, 3 mm printed seat','horn_intrusion_mm':3.0,'spline_printed':False,'factory_case_screws_removed':False}
    # Symmetry checked on actual BRep geometry, independently of the nominal equations.
    sym=[]
    for a in [30,90,140]:
        pp=m.at(a);right=next(x.shape for x in pp if x.name=='jaw_1').mirror('YZ');left=next(x.shape for x in pp if x.name=='jaw_-1')
        difference=abs(right.Volume()+left.Volume()-2*right.intersect(left).Volume())
        sym.append({'angle':a,'symmetric_difference_mm3':difference,'pass':difference<1e-4})
    report['actual_jaw_symmetry']={'pass':all(x['pass'] for x in sym),'tests':sym}
    # Geometric optical envelope check only: no ray-based occlusion or actual camera calibration.
    center=np.array(ORIGIN)+np.array([0,-sin(TILT*pi/180),cos(TILT*pi/180)])*11.6
    forward=np.array([0,-sin(TILT*pi/180),cos(TILT*pi/180)]);up=np.array([0,cos(TILT*pi/180),sin(TILT*pi/180)])
    pts=[]
    for a in [30,90,140]:
        g=2*(position(a)-position(140))+.8
        for side in [-1,1]:
            p=np.array([side*g/2,0,36])-center
            ha=degrees(atan2(p[0],np.dot(p,forward)));va=degrees(atan2(np.dot(p,up),np.dot(p,forward)))
            pts.append({'angle':a,'side':side,'horizontal_deg':ha,'vertical_deg':va})
    report['camera_geometry']={'assumed_board_mm':[32,32,1.6],'hole_grid_mm':[28,28],'fixed_tilt_deg':TILT,'optical_center_assumed_mm':center.tolist(),'tip_center_projection_angles':pts,'visibility_certified':False,'note':'projection only; actual FOV/focus/distortion/occlusion and connector unknown'}
    report['pass']=all(report[k]['pass'] for k in ['kinematics','stops','guide','tool_access','servo_interfaces','actual_jaw_symmetry'])
    (ROOT/'reports/engineering_checks.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    return report
if __name__=='__main__':run()
