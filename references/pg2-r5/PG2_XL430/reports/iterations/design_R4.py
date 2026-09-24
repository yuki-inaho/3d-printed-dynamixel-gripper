"""PG2: upright XL430, printed rectangular guides. Coordinates and units: mm; Y up, Z forward.
This is a digital prototype, not a validated load-bearing product.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from math import sin,cos,sqrt,pi,atan2,degrees
import json
from functools import lru_cache
import cadquery as cq

ROOT=Path(__file__).resolve().parents[1]
@dataclass(frozen=True)
class Parameters:
    motor:str='DYNAMIXEL XL430-W250'
    revision:str='R4'
    r:float=15.0
    L:float=36.0
    open_angle:float=30.0
    close_angle:float=140.0
    closed_gap:float=0.8
    face_width:float=136.0
    face_height:float=84.0
    jaw_width:float=28.0
    jaw_y:float=36.0
    jaw_back:float=4.8
    jaw_top:float=9.0
    guide_rear:float=4.5
    retainer_bottom:float=9.4
    link_bottom:float=9.3
    link_thickness:float=4.0
    shoulder_top:float=13.5
    finger_tip:float=36.0
    output_axis:tuple=(0,0,1)
    finger_axis:tuple=(0,0,1)
    motor_long_axis:tuple=(0,1,0)
    guide_material:str='printed_polymer'
    guide_type:str='rectangular_captured_slide'
    body_side_fastener:str='PHS M2.6x5 TAP'
P=Parameters()

def box(x0,x1,y0,y1,z0,z1):
    return cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,cq.Vector(x0,y0,z0))
def cyl(r,h,x=0,y=0,z=0,axis=(0,0,1)):
    return cq.Solid.makeCylinder(r,h,cq.Vector(x,y,z),cq.Vector(*axis))
def fuse(*s):
    o=s[0]
    for q in s[1:]:o=o.fuse(q)
    return o.clean()
def cut(s,*q):
    for v in q:s=s.cut(v)
    return s.clean()
def xy_poly(points,z,h):
    return cq.Workplane('XY',origin=(0,0,z)).polyline(points).close().extrude(h).val()
def xz_poly(points,y,depth):
    # points are (x,z); extrude along +Y
    w=cq.Wire.makePolygon([cq.Vector(x,y,z) for x,z in points]+[cq.Vector(points[0][0],y,points[0][1])])
    return cq.Solid.extrudeLinear(w,[],cq.Vector(0,depth,0))
@lru_cache(maxsize=256)
def hex_nut(x,y,z,af=5.5,h=2.4,bore=1.5):
    rr=af/sqrt(3)
    pts=[(x+rr*cos(k*pi/3),y+rr*sin(k*pi/3)) for k in range(6)]
    return cut(xy_poly(pts,z,h),cyl(bore,h+.2,x,y,z-.1))
def nut_pocket(x,y,z,h=2.6,af=5.9):
    rr=af/sqrt(3)
    return xy_poly([(x+rr*cos(k*pi/3),y+rr*sin(k*pi/3)) for k in range(6)],z,h)
@lru_cache(maxsize=256)
def bolt(d,L,x,y,seat,head_d=None,head_h=None,countersunk=False,drive='hex'):
    head_d=head_d or d*1.9;head_h=head_h or d
    if countersunk:
        # L includes flat head; seat is flush top surface
        hd=(head_d-d)/2
        h=cq.Solid.makeCone(d/2,head_d/2,hd,cq.Vector(x,y,seat-hd))
        bb=fuse(cyl(d/2,L-hd,x,y,seat-L),h)
        rr=1.18
        return bb.cut(xy_poly([(x+rr*cos(k*pi/3),y+rr*sin(k*pi/3)) for k in range(6)],seat-.8,1.0)).clean()
    ss=fuse(cyl(d/2,L,x,y,seat-L),cyl(head_d/2,head_h,x,y,seat))
    # Hex recess for visualization/tool-axis check; supplier pan-head exceptions use head envelope.
    if drive=='cross':
        return cut(ss,box(x-head_d*.32,x+head_d*.32,y-.32,y+.32,seat+head_h*.45,seat+head_h+.1),box(x-.32,x+.32,y-head_d*.32,y+head_d*.32,seat+head_h*.45,seat+head_h+.1))
    rr=d*.4/cos(pi/6)
    tool=xy_poly([(x+rr*cos(k*pi/3),y+rr*sin(k*pi/3)) for k in range(6)],seat+head_h*.5,head_h)
    return ss.cut(tool).clean()
def frame(p=P):
    # Full-width back bearing rails + ends. Central void permits fastener ends and servo horn.
    s=cut(box(-68,68,-42,42,.5,4.5),box(-61.2,61.2,-28,28,0,5))
    s=fuse(s,box(-68,68,36.6,42,4.5,9.4),box(-68,68,-42,-36.2,4.5,9.4))
    # End stop fences: bound jaw at approximately 23.9..142.7 degrees (not to be driven against).
    s=fuse(s,box(-68,-63.2,-36.2,36.6,4.5,9.4),box(63.2,68,-36.2,36.6,4.5,9.4))
    s=fuse(s,box(-8.9,8.9,28,32,4.5,9),box(-8.9,8.9,-32,-28,4.5,9))
    for y in [-38.5,38.5]:
        for x in [-64,-21,21,64]:
            s=cut(s,cyl(1.7,10,x,y,.3),box(x-3.4,x+3.4,y-2.95,y+2.95,.4,3.1))
    for x in [-8,8]:
        s=cut(s,cyl(1.7,10,x,38.5,.3),box(x-3.4,x+3.4,35.55,41.45,.4,3.1))
    for x in [-23,23]:
        for y in [-32,32]:
            s=cut(s,cyl(1.7,5,x,y,.3),cq.Solid.makeCone(1.7,3.3,1.6,cq.Vector(x,y,2.9)))
    return s

def retainer():
    s=box(-68,68,32,42,9.4,12.4)
    for x in [-64,-21,21,64]:s=cut(s,cyl(1.7,3.4,x,38.5,9.2))
    # Two optional camera dock clearance holes (nuts are added only in camera kit).
    for x in [-8,8]:s=cut(s,cyl(1.7,3.4,x,38.5,9.2))
    return s

def jaw(p=P):
    c=position(p.close_angle,p)-p.closed_gap/2
    z0=p.jaw_back
    s=fuse(box(-14,14,22,36,z0,9),box(-14,14,-36,-22,z0,9),
           box(5.5,14,-23,23,z0,9),cyl(5.5,9-z0,z=z0),box(0,14,-5.5,5.5,z0,9))
    # Short open window: big pads at front, no slender projecting fingers.
    plate=cut(box(-c,-c+8,-32,32,18,p.finger_tip),box(-c-.1,-c+8.1,-20,20,23,30))
    plate=cq.Workplane(obj=plate).edges("|X").fillet(2).val()
    prof=[(-14,8),(14,8),(14,14),(-c+8,23),(-c,23),(-c,18),(-14,18)]
    s=fuse(s,plate,xz_poly(prof,22,10),xz_poly(prof,-32,10),cyl(3,p.shoulder_top-9,z=9))
    s=cut(s,cyl(1.7,10,z=z0-.2),nut_pocket(0,0,z0-.1,2.7))
    return s

def crank(p=P):
    # Arms are the envelope of fixed bore centers, not a cam profile.
    s=fuse(cyl(11,9),box(-p.r,p.r,-5.5,5.5,4,9),cyl(5.5,5,p.r,0,4),cyl(5.5,5,-p.r,0,4))
    s=cut(s,cyl(4.5,10,z=-.1))
    for x,y in [(8,0),(-8,0),(0,8),(0,-8)]:
        s=cut(s,cyl(1.15,10,x,y,-.2),cyl(2.3,6.2,x,y,3))
    for x in [-p.r,p.r]:
        s=fuse(s,cyl(3,p.shoulder_top-9,x,0,9))
        s=cut(s,cyl(1.7,11,x,0,3),nut_pocket(x,0,3.9,2.7))
    return s

def link(p=P):
    # local endpoints at (0,0),(L,0), bowed +Y for packaging.
    L=p.L
    pts=[(0,0),(.22*L,4),(.5*L,6),(.78*L,4),(L,0)]
    segments=[]
    for (x1,y1),(x2,y2) in zip(pts,pts[1:]):
        dx,dy=x2-x1,y2-y1;d=sqrt(dx*dx+dy*dy);nx,ny=-dy/d*3.5,dx/d*3.5
        segments.append(xy_poly([(x1+nx,y1+ny),(x2+nx,y2+ny),(x2-nx,y2-ny),(x1-nx,y1-ny)],p.link_bottom,p.link_thickness))
    for x,y in pts:segments.append(cyl(3.5,p.link_thickness,x,y,p.link_bottom))
    for x in [0,L]:segments.append(cyl(5.4,p.link_thickness,x,0,p.link_bottom))
    return cut(fuse(*segments),cyl(3.2,5,0,0,9),cyl(3.2,5,L,0,9))

def mount():
    s=box(-27,27,-37,36,-1.5,.5)
    s=cut(s,cyl(11.4,3,z=-2))
    # Bilateral saddles using ORIGINAL side pilot holes, not case-cover screws.
    for side in [-1,1]:
        wall=box(14.5,18.5,-35.25,11.25,-17,-1.5)
        if side<0:wall=wall.mirror('YZ')
        s=fuse(s,wall)
        for y in [-28,-4]:
            if side>0:
                s=cut(s,cyl(1.5,5,14,y,-13,(1,0,0)),cyl(2.8,2.1,16.5,y,-13,(1,0,0)))
            else:
                s=cut(s,cyl(1.5,5,-14,y,-13,(-1,0,0)),cyl(2.8,2.1,-16.5,y,-13,(-1,0,0)))
    for x in [-23,23]:
        for y in [-32,32]:
            s=fuse(s,box(x-4,x+4,y-4,y+4,-5,-1.5))
            s=cut(s,cyl(1.7,6,x,y,-5.1),nut_pocket(x,y,-5.1,2.7))
    # Cable ports are behind the walls: headers sit z=-28.8..-19.6.
    return s

def position(a,p=P):
    t=a*pi/180
    return p.r*cos(t)+sqrt(p.L*p.L-(p.r*sin(t))**2)
def point(a,p=P):
    t=a*pi/180
    return p.r*cos(t),p.r*sin(t)
def pose(s,angle=0,x=0,y=0,z=0):
    return s.rotate((0,0,0),(0,0,1),angle).translate((x,y,z))
@dataclass
class Part:
    name:str
    shape:cq.Shape
    color:tuple
    group:str
    material:str
    role:str

def supplier():
    # Source CAD has its output dummy fused to the case; geometrically separate only the top horn envelope.
    src=cq.importers.importStep(str(ROOT/'reference/core_0.step')).val().translate((0,0,-19))
    region=cyl(10.3,6,z=-3.5)
    horn=src.intersect(region)
    body=src.cut(region)
    # Other supplier occurrences preserved for visualization; excluded from supplier internal interference checks.
    source=json.loads((ROOT/'reference/source_parts.json').read_text())
    extras=[]
    for row in source[1:]:
        path=ROOT/'reference'/f"{row['name']}.step"
        extras.append(cq.importers.importStep(str(path)).val().translate((0,0,-19)))
    core1=cq.importers.importStep(str(ROOT/'reference/core_1.step')).val().translate((0,0,-19))
    # Compounding keeps fasteners and connector detail without expensive noisy vendor Boolean unions.
    return cq.Compound.makeCompound([body,core1]+extras),horn

class Model:
    def __init__(self,p=P):
        self.p=p
        self.printed={'01_frame':frame(p),'02_retainer':retainer(),'03_jaw':jaw(p),'04_crank':crank(p),'05_link':link(p),'06_motor_mount':mount()}
        self.motor,self.horn=supplier()
        self.fixed=[]
        self.add('frame',self.printed['01_frame'],(.22,.25,.3),'fixed','printed_polymer','guide')
        self.add('retainer_top',self.printed['02_retainer'],(.28,.31,.36),'fixed','printed_polymer','guide_capture')
        self.add('retainer_bottom',pose(self.printed['02_retainer'],180),(.28,.31,.36),'fixed','printed_polymer','guide_capture')
        self.add('motor_mount',self.printed['06_motor_mount'],(.24,.27,.32),'fixed','printed_polymer','motor_mount')
        self.add('XL430_W250',self.motor,(.13,.15,.19),'supplier','supplier','actuator')
        for y in [-38.5,38.5]:
            for x in [-64,-21,21,64]:
                self.add(f'rail_bolt_{x}_{y}',bolt(3,12,x,y,12.4,5.5,3),(.63,.65,.68),'fixed','steel','fastener')
                self.add(f'rail_nut_{x}_{y}',hex_nut(x,y,.6),(.59,.61,.64),'fixed','steel','fastener')
        for x in [-23,23]:
            for y in [-32,32]:
                self.add(f'mount_bolt_{x}_{y}',bolt(3,10,x,y,4.5,6,1.5,True),(.64,.66,.69),'fixed','steel','fastener')
                self.add(f'mount_nut_{x}_{y}',hex_nut(x,y,-4.9),(.6,.62,.65),'fixed','steel','fastener')
        for side in [-1,1]:
            for y in [-28,-4]:
                b=bolt(2.6,5,0,0,0,5,1.8,drive='cross')
                # local +Z becomes outward +/-X. head seated at wall counterbore floor x=+/-16.5.
                b=b.rotate((0,0,0),(0,1,0),90*side).translate((16.5*side,y,-13))
                self.add(f'servo_tap_{side}_{y}',b,(.66,.68,.72),'fixed','steel','servo_body_tap')
    def add(self,n,s,c,g,m,r):self.fixed.append(Part(n,s,c,g,m,r))
    def at(self,a):
        p=self.p; arr=self.fixed.copy();x=position(a,p);ax,ay=point(a,p)
        def put(n,s,c,g,role,material='printed_polymer'):
            arr.append(Part(n,s,c,g,material,role))
        put('horn',pose(self.horn,a),(.29,.30,.32),'rotor','supplier_horn','supplier')
        put('crank',pose(self.printed['04_crank'],a),(.95,.4,.1),'rotor','crank')
        for hx,hy in [(8,0),(-8,0),(0,8),(0,-8)]:
            put(f'horn_M2_{hx}_{hy}',pose(bolt(2,6,hx,hy,3,4,1.6,drive='cross'),a),(.68,.70,.73),'rotor','fastener','steel')
        for side,rotation in [(1,0),(-1,180)]:
            put(f'jaw_{side}',pose(self.printed['03_jaw'],rotation,side*x),(.88,.27,.1),f'jaw_{side}','jaw')
            ang=degrees(atan2(-ay,x-ax))
            put(f'link_{side}',pose(self.printed['05_link'],ang+rotation,side*ax,side*ay),(.21,.63,.48),f'link_{side}','connecting_link')
            for kind,px,py,grp in [('crank',side*ax,side*ay,'rotor'),('jaw',side*x,0,f'jaw_{side}')]:
                # Nuts rotate with their host. Crank pockets follow crank angle.
                localrot=a if kind=='crank' else rotation
                b=bolt(3,12 if kind=='crank' else 10,0,0,14,5.5,3)
                n=hex_nut(0,0,4.2 if kind=='crank' else 5.0)
                washer=cut(cyl(3.5,.5,z=13.5),cyl(1.6,.7,z=13.4))
                put(f'{kind}_pivot_bolt_{side}',pose(b,localrot,px,py),(.66,.68,.72),grp,'fastener','steel')
                put(f'{kind}_pivot_nut_{side}',pose(n,localrot,px,py),(.61,.63,.66),grp,'fastener','steel')
                put(f'{kind}_pivot_washer_{side}',pose(washer,localrot,px,py),(.61,.63,.66),grp,'fastener','steel')
        return arr

def assembly(parts):
    a=cq.Assembly(name='PG2_XL430')
    for p in parts:a.add(p.shape,name=p.name,color=cq.Color(*p.color))
    return a

if __name__=='__main__':
    m=Model();print('printable:',[(n,len(s.Solids()),round(s.Volume())) for n,s in m.printed.items()])
    print('opening', [(a,2*(position(a)-position(P.close_angle))+P.closed_gap) for a in [30,90,150]])
    assembly(m.at(85)).save(str(ROOT/'CAD/PG2_working.step'))
