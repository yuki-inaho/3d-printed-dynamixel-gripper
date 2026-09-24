from design import *

def retainer_variant(total_gap):
    """Retainer feet remain at 9.4; only underside of capture lip changes."""
    if total_gap not in [.5,.7,.9]:raise ValueError('Allowed clearances are 0.5, 0.7, 0.9 mm total, not per face.')
    s=retainer();new_z=4.5+(9-4.8)+total_gap
    if new_z<9.4:s=fuse(s,box(-68,68,33,36.15,new_z,9.4))
    elif new_z>9.4:s=cut(s,box(-68.1,68.1,32.9,36.15,9.3,new_z))
    return s

def gauge():
    s=box(-36,36,0,15,0,20)
    for x,c,d in [(-24,.5,6.2),(0,.7,6.4),(24,.9,6.6)]:
        s=cut(s,box(x-5.4,x+5.4,-.1,15.1,2,6.2+c),cyl(d/2,15.2,x,-.1,13,(0,1,0)))
    return s

def tongue():
    s=fuse(box(-5,5,0,27,0,4.2),box(-10,10,22,30,0,4.2),cyl(3,4.5,0,26,4.2))
    return cut(s,cyl(1.7,9,0,26,-.1))

def print_pose(name,s):
    # Flatten only orientation/translation; no geometry repair or scaling.
    if 'jaw' in name:s=s.rotate((0,0,0),(0,1,0),-90)
    elif 'motor_mount' in name or 'camera_stand' in name or 'retainer' in name:s=s.rotate((0,0,0),(1,0,0),180)
    elif 'gauge' in name:s=s.rotate((0,0,0),(1,0,0),90)
    b=s.BoundingBox();return s.translate((-b.xmin,-b.ymin,-b.zmin))
