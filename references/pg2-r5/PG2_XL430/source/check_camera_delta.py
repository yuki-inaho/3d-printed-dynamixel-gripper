"""Supplementary current-camera interference and optical-ray validation.
The separate current-revision 111-pose sweep covers the complete assembly.
Do not relabel the older C1 camera sweep as a new camera test.
"""
from design import *
from camera import optional_parts,cam_pose,TILT,ORIGIN,CAMERA_REVISION
from guardrails import geometry
from assembly_reader import bounds
from review_iteration import overlap_bbox
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCP.gp import gp_Pnt,gp_Dir,gp_Lin
import numpy as np,json,hashlib,itertools,time

m=Model();cam=optional_parts();geometry(m,m.at(30)+cam)
report={'core_revision':P.revision,'camera_revision':CAMERA_REVISION,'geometry_changes':'supplementary camera-vs-core and camera internal validation; complete current-revision sweep is separate','angles':list(range(30,141)),'collisions':[]}
cb=[bounds(r.shape) for r in cam];done=set();nb=0
for a in range(30,141):
    base=m.at(a);bb=[bounds(r.shape) for r in base]
    for i,c in enumerate(cam):
        for j,b in enumerate(base):
            key=(c.name,b.name)
            if b.group in ['fixed','supplier']:
                if key in done:continue
                done.add(key)
            if not overlap_bbox(cb[i],bb[j]):continue
            v=c.shape.intersect(b.shape).Volume();nb+=1
            if v>1e-4:report['collisions'].append({'angle':a,'a':c.name,'b':b.name,'volume':v})
    if a%10==0:print('camera delta',a,'hits',len(report['collisions']),flush=True)
for i,j in itertools.combinations(range(len(cam)),2):
    if overlap_bbox(cb[i],cb[j]):
        v=cam[i].shape.intersect(cam[j].shape).Volume();nb+=1
        if v>1e-4:report['collisions'].append({'angle':'fixed','a':cam[i].name,'b':cam[j].name,'volume':v})
report['boolean_tests']=nb
forward=np.array([0,-sin(TILT*pi/180),cos(TILT*pi/180)]);up=np.array([0,cos(TILT*pi/180),sin(TILT*pi/180)]);center=np.array(ORIGIN)+forward*11.6
hfov=80.;vfov=degrees(2*atan2(tan(hfov*pi/360)*3,4)) if False else degrees(2*np.arctan(np.tan(hfov*pi/360)*.75))
raytests=[]
for a in [30,90,140]:
    rows=m.at(a)+cam;compound=cq.Compound.makeCompound([r.shape for r in rows]);inter=IntCurvesFace_ShapeIntersector();inter.Load(compound.wrapped,1e-7)
    gap=2*(position(a)-position(140))+.8
    for side in [-1,1]:
        for y,z in itertools.product([-12,0,12],[31,33,35]):
            target=np.array([side*gap/2,y,z]);d=target-center;L=float(np.linalg.norm(d));u=d/L
            ha=degrees(np.arctan2(d[0],np.dot(d,forward)));va=degrees(np.arctan2(np.dot(d,up),np.dot(d,forward)))
            start=center+u*.1;line=gp_Lin(gp_Pnt(*start),gp_Dir(*u));inter.Perform(line,0,L-.25)
            occ=[]
            for k in range(1,inter.NbPnt()+1):
                t=inter.WParameter(k)
                if 1e-6<t<L-.25:occ.append(t)
            raytests.append({'angle':a,'side':side,'target':target.tolist(),'horizontal_deg':ha,'vertical_deg':va,'intersections_before_target':len(occ),'pass':not occ and abs(ha)<hfov/2 and abs(va)<vfov/2})
report['optical_model']={'horizontal_fov_deg':hfov,'vertical_fov_deg':vfov,'optical_center_mm':center.tolist(),'rays':raytests,'pass':all(x['pass'] for x in raytests),'scope':'CAD ray and ideal FOV only; actual lens, focus, cable and full finger visibility not certified'}
report['pass']=not report['collisions'] and report['optical_model']['pass']
(ROOT/f'reports/camera_{CAMERA_REVISION}_delta.json').write_text(json.dumps(report,indent=2));print('PASS',report['pass'], 'ray passes',sum(x['pass'] for x in raytests),len(raytests),flush=True)
assert report['pass']
