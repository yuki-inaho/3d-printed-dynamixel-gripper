"""Rigid group motion from a 90-degree reference; tested against direct construction."""
import math,numpy as np
from design import Item,P,pos,turn,world

def pose(ref,a,world_coords=False):
    if not P.theta_open<=a<=P.theta_close:raise ValueError('unreviewed angle')
    t=math.radians(a);A=P.r*np.array([math.cos(t),math.sin(t)])
    Q=np.array([pos(a),0.]);phi=math.degrees(math.atan2((Q-A)[1],(Q-A)[0]))
    A0=np.array([0.,P.r]);phi0=math.degrees(math.atan2(-P.r,pos(90)))
    dp=math.radians(phi-phi0);rot=np.array([[math.cos(dp),-math.sin(dp)],[math.sin(dp),math.cos(dp)]])
    result=[]
    for it in ref:
        s=it.shape
        if it.group=='drive':s=turn(s,a-90)
        elif it.group in ['R','L']:s=s.translate(((1 if it.group=='R' else -1)*(pos(a)-pos(90)),0,0))
        elif it.group.startswith('link_'):
            sg=1 if it.group=='link_R' else -1
            sh=sg*(A-rot@A0);s=turn(s,phi-phi0).translate((float(sh[0]),float(sh[1]),0))
        result.append(Item(it.name,world(s) if world_coords else s,it.group,it.kind,it.color))
    return result
