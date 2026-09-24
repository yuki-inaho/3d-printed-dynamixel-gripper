"""Optional, fixed 25-degree camera saddle. Generic 32 mm board, 28 mm hole grid.
Optics and plug clearance are assumptions; this does not certify a particular camera.
"""
from design import *

def cam_pose(s):return s.rotate((0,0,0),(1,0,0),25).translate((0,51,-22))
def plate():
    s=box(-23,23,-19,19,-3,0)
    # Open center for lens back / component clearance; not a solid pad under electronics.
    s=cut(s,box(-10,10,-10,10,-3.2,.2))
    for x in [-14,14]:
        for y in [-14,14]:
            s=fuse(s,cyl(3,2,x,y,0))
            s=cut(s,cyl(1.2,5.4,x,y,-3.2),nut_pocket(x,y,-3.1,1.9,4.4))
    for x in [-19,19]:s=cut(s,cyl(1.7,3.4,x,0,-3.2))
    return s

def stand():
    foot=fuse(box(-12,12,34.5,47,12.4,15.4),box(-23,23,42,47,12.4,15.4))
    for x in [-8,8]:foot=cut(foot,cyl(1.7,4,x,38.5,12.2))
    prof=[(42,12.4),(47,15.4),(58,-29),(50,-33),(45,8)] # Y,Z
    # extrude shape along X
    wire=cq.Wire.makePolygon([cq.Vector(15,y,z) for y,z in prof]+[cq.Vector(15,*prof[0])])
    arm=cq.Solid.extrudeLinear(wire,[],cq.Vector(8,0,0))
    s=fuse(foot,arm,arm.mirror('YZ'))
    # Trim the arms to the plate seating plane; the excluded envelope is explicit.
    s=cut(s,cam_pose(box(-24,24,-20,20,-3,5)))
    for side in [-1,1]:
        lug=box(15,23,-5,5,-10,-3)
        if side<0:lug=lug.mirror('YZ')
        lug=cut(lug,cyl(1.7,7.4,side*19,0,-10.2),nut_pocket(side*19,0,-10.1,2.7))
        s=fuse(s,cam_pose(lug))
    return s

def optional_parts():
    out=[]
    def put(n,s,c,r,m='printed_polymer'):out.append(Part(n,s,c,'camera',m,r))
    put('camera_stand',stand(),(.27,.30,.35),'camera_mount')
    put('camera_plate',cam_pose(plate()),(.3,.33,.38),'camera_mount')
    for x in [-8,8]:
        put(f'camera_foot_M3_{x}',bolt(3,16,x,38.5,15.4,5.5,3),(.66,.68,.72),'fastener','steel')
        put(f'camera_foot_nut_{x}',hex_nut(x,38.5,.6),(.64,.66,.69),'fastener','steel')
    for x in [-19,19]:
        put(f'camera_plate_M3_{x}',cam_pose(bolt(3,10,x,0,0,5.5,3)),(.66,.68,.72),'fastener','steel')
        put(f'camera_plate_nut_{x}',cam_pose(hex_nut(x,0,-9.8)),(.64,.66,.69),'fastener','steel')
    pcb=box(-16,16,-16,16,2,3.6)
    for x in [-14,14]:
        for y in [-14,14]:pcb=cut(pcb,cyl(1.15,2,x,y,1.8))
    put('camera_PCB_ASSUMED',cam_pose(pcb),(.11,.34,.25),'camera_envelope','electronics')
    put('camera_lens_ASSUMED',cam_pose(fuse(box(-6,6,-6,6,3.6,7.6),cyl(5,4,z=7.6))),(.12,.14,.17),'camera_envelope','electronics')
    for x in [-14,14]:
        for y in [-14,14]:
            put(f'camera_M2_{x}_{y}',cam_pose(bolt(2,8,x,y,3.6,3.8,2)),(.66,.68,.72),'fastener','steel')
            put(f'camera_M2_nut_{x}_{y}',cam_pose(hex_nut(x,y,-2.8,4,1.6,1)),(.64,.66,.69),'fastener','steel')
    return out

if __name__=='__main__':
    from render import render
    for n,s in [('stand',stand()),('plate',plate())]:print(n,len(s.Solids()),s.isValid(),s.Volume())
    m=Model(); render(m.at(55)+optional_parts(),ROOT/'images/camera_working.png',scale=76,cam=(150,130,210),target=(0,10,0))
    assembly(m.at(55)+optional_parts()).save(str(ROOT/'CAD/camera_working.step'))
