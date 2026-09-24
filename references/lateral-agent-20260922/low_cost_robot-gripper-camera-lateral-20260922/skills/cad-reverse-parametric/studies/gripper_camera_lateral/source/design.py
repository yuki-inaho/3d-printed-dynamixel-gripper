"""Source-preserving lateral gripper + exchangeable wrist-camera carrier.

Dimensions: mm, angles: degrees. H is the original static-jaw local frame:
+X = image right, +Y = fingers forward, +Z = jaw hinge axis / camera side.
No imported jaw/servo B-rep is remodelled. Only new printed parts are generated.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import cadquery as cq
import numpy as np

STUDY = Path(__file__).resolve().parents[1]
TOOLKIT = STUDY.parents[1]
REPO = TOOLKIT.parents[1]
BASE_SOURCE = STUDY.parent / "follower_geometry_revision/source"
if str(BASE_SOURCE) not in sys.path:
    sys.path.insert(0, str(BASE_SOURCE))
from assembly_io import bounds, read_step
from rebuild import build_geometry, unique_occurrence, require_single_solid, verify_sources

DEFAULT_OUT = TOOLKIT / "outputs/gripper_camera_lateral/unaccepted/20260922-r1"
MOUNT_CENTER = np.array([0.750000268220905, -19.999999791407, 14.75])
PIVOT = np.array([8.150000268220927, -6.849999475307118, 3.4])
MOUNT_POINTS = np.array([
    [MOUNT_CENTER[0], MOUNT_CENTER[1], 8.75],
    [MOUNT_CENTER[0] + 6, MOUNT_CENTER[1], 14.75],
    [MOUNT_CENTER[0] - 6, MOUNT_CENTER[1], 14.75],
    [MOUNT_CENTER[0], MOUNT_CENTER[1], 20.75],
])


def volume(s: cq.Shape) -> float:
    return sum(x.Volume() for x in s.Solids())


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_config(path: Path | None = None) -> dict:
    c = json.loads((path or STUDY / "design.json").read_text())
    for key, val in c.items():
        if isinstance(val, (float, int)) and not isinstance(val, bool) and not math.isfinite(val):
            raise ValueError(f"Nonfinite configuration: {key}")
    if c["clocking_deg"] != 90 or c["flange_thickness_mm"] != 4:
        raise ValueError("Only the measured 90-degree, 4-mm interface is supported; revalidate other datums")
    if not 25 <= c["camera_tilt_down_deg"] <= 55:
        raise ValueError("Camera tilt outside the supported prototype parameter range")
    if c["camera_hole_pitch_mm"] != 28:
        raise ValueError("This carrier is specifically for a 28 x 28 mm hole pattern")
    if not 0 < c["opening_max_deg"] <= 50:
        raise ValueError("Opening beyond 50 degrees is outside this study's reviewed range")
    for k in ("assumed_hfov_deg", "assumed_vfov_deg"):
        if not 1 < c[k] < 160:
            raise ValueError(f"Invalid field of view: {k}")
    for k in ("motion_sample_step_deg", "vision_sample_step_deg"):
        if not 0.1 <= c[k] <= 5:
            raise ValueError(f"Unsupported sampling interval: {k}")
    origin = np.asarray(c["camera_carrier_origin_mm"], dtype=float)
    if origin.shape != (3,) or not np.isfinite(origin).all():
        raise ValueError("Camera origin must be three finite millimetre coordinates")
    # These dimensions are a reviewed part family, not unrestricted parameters.
    # Reject edits that hard-coded mating features would otherwise silently ignore.
    fixed = {"flange_outer_radius_mm":12, "flange_bore_mm":2.3,
             "carrier_thickness_mm":3, "pcb_spacer_mm":4,
             "camera_board_width_mm":32, "camera_board_thickness_mm":1.6,
             "camera_lens_length_mm":8, "camera_lens_radius_mm":8,
             "pcb_screw_clearance_mm":2.3, "pcb_nut_af_clearance_mm":4.25,
             "pcb_nut_pocket_depth_mm":1.8, "carrier_screw_clearance_mm":3.2,
             "carrier_nut_af_clearance_mm":5.7, "carrier_nut_pocket_depth_mm":2.5}
    for key, expected in fixed.items():
        if c[key] != expected:
            raise ValueError(f"{key} requires a reviewed new part family, not an unchecked config edit")
    # These flags cannot themselves grant engineering approval.
    return c


def rotate_about(point, axis, deg) -> cq.Location:
    p = np.asarray(point, dtype=float)
    return cq.Location(tuple(p)) * cq.Location((0, 0, 0), tuple(axis), deg) * cq.Location(tuple(-p))


def camera_basis(c):
    a = math.radians(c["camera_tilt_down_deg"])
    right = np.array([1., 0., 0.])
    up = np.array([0., math.sin(a), math.cos(a)])
    forward = np.array([0., math.cos(a), -math.sin(a)])
    return right, up, forward


def camera_point(c, u=0., v=0., w=0.):
    r, up, d = camera_basis(c)
    return np.asarray(c["camera_carrier_origin_mm"]) + u*r + v*up + w*d


def camera_plane(c, w=0.):
    # The plane's local +v is DOWN because right x down = optical forward.
    # Public coordinates use up, so sketch v is explicitly sign-reversed below.
    _, _, d = camera_basis(c)
    return cq.Plane(origin=tuple(camera_point(c, w=w)), xDir=(1, 0, 0), normal=tuple(d))


def camera_rect(c, width, height, vcenter=0., w=0., thickness=3.):
    return cq.Workplane(camera_plane(c, w)).center(0, -vcenter).rect(width, height).extrude(thickness).val()


def camera_cylinder(c, u, v, w, radius, height):
    d = camera_basis(c)[2]
    return cq.Solid.makeCylinder(radius, height, cq.Vector(*camera_point(c,u,v,w)), cq.Vector(*d))


def camera_hex(c, u, v, w, across_flats, height):
    # CadQuery polygon diameter is its circumscribed-circle diameter.
    return (cq.Workplane(camera_plane(c, w)).center(u,-v)
            .polygon(6, 2*across_flats/math.sqrt(3)).extrude(height).val())


def camera_optical_center(c):
    w = c["carrier_thickness_mm"] + c["pcb_spacer_mm"] + c["camera_board_thickness_mm"] + c["camera_lens_length_mm"]
    return camera_point(c, w=w)


def make_parts(c):
    # 4-mm interface sits between existing horn and unchanged gripper rear face.
    flange = cq.Solid.makeCylinder(
        c["flange_outer_radius_mm"], c["flange_thickness_mm"],
        cq.Vector(MOUNT_CENTER[0], MOUNT_CENTER[1]-4, MOUNT_CENTER[2]), cq.Vector(0,1,0))
    bridge_beam = camera_rect(c, 40, 10, vcenter=-24, w=-4, thickness=4)
    struts = []
    top = camera_point(c, v=-28, w=-2)
    for xb, xt in ((MOUNT_CENTER[0]-6,top[0]-4), (MOUNT_CENTER[0]+6,top[0]+4)):
        # Two straight, non-organic lofts; lower ends overlap the flange.
        loft = (cq.Workplane("XY", origin=(0,0,22))
                .center(xb, MOUNT_CENTER[1]-2).rect(6,4)
                .workplane(offset=float(top[2]-22)).center(float(xt-xb), float(top[1]-(MOUNT_CENTER[1]-2))).rect(6,6)
                .loft(combine=True).val())
        struts.append(loft)
    bridge = flange.fuse(bridge_beam,*struts).clean()
    # Trim the strut corner overrun at the actual carrier mating plane.
    # A zero-thickness contact is allowed; overlapping separate printed parts is not.
    bridge = bridge.cut(camera_rect(c, 40, 48, vcenter=-5, w=0, thickness=20)).clean()
    for p in MOUNT_POINTS:
        bridge = bridge.cut(cq.Solid.makeCylinder(c["flange_bore_mm"]/2,4.4,
                          cq.Vector(p[0],MOUNT_CENTER[1]-4.2,p[2]),cq.Vector(0,1,0)))
    for u in (-12.,12.):
        bridge = bridge.cut(camera_cylinder(c,u,-24,-4.2,c["carrier_screw_clearance_mm"]/2,4.4))
        bridge = bridge.cut(camera_hex(c,u,-24,-4.1,c["carrier_nut_af_clearance_mm"],2.6))
    # Cable-tie windows through the top beam, away from screws and structure.
    for u in (-4.5,4.5):
        tool = (cq.Workplane(camera_plane(c,-4.1)).center(u,24)
                .rect(2,5).extrude(4.2).val())
        bridge = bridge.cut(tool)
    bridge=bridge.clean()

    # Interchangeable 28-mm-pitch camera carrier. The central aperture clears
    # board-back electronics; real component-height limits remain unverified.
    carrier = camera_rect(c,38,38,thickness=c["carrier_thickness_mm"])
    carrier = carrier.fuse(camera_rect(c,34,10,vcenter=-24,thickness=3)).clean()
    carrier = carrier.cut(camera_rect(c,24,24,w=-.1,thickness=3.2))
    half=c["camera_hole_pitch_mm"]/2
    for u in (-half,half):
        for v in (-half,half):
            carrier=carrier.cut(camera_cylinder(c,u,v,-.1,c["pcb_screw_clearance_mm"]/2,3.2))
            carrier=carrier.cut(camera_hex(c,u,v,-.1,c["pcb_nut_af_clearance_mm"],1.9))
    for u in (-12.,12.):
        carrier=carrier.cut(camera_cylinder(c,u,-24,-.1,c["carrier_screw_clearance_mm"]/2,3.2))
    carrier=carrier.clean()

    spacer = camera_rect(c,36,36,w=3,thickness=c["pcb_spacer_mm"])
    spacer=spacer.cut(camera_rect(c,24,24,w=2.9,thickness=c["pcb_spacer_mm"]+.2))
    for u in (-half,half):
        for v in (-half,half):
            spacer=spacer.cut(camera_cylinder(c,u,v,2.9,c["pcb_screw_clearance_mm"]/2,c["pcb_spacer_mm"]+.2))
    spacer=spacer.clean()
    result={"wrist_camera_bridge":bridge, "uvc28_camera_carrier":carrier, "uvc28_pcb_spacer_4mm":spacer}
    for n,s in result.items():require_single_solid(s,n)
    return result


def camera_proxies(c):
    """Explicitly ASSUMED envelope only; never presented as supplier camera CAD."""
    w=3+c["pcb_spacer_mm"]
    pcb=camera_rect(c,c["camera_board_width_mm"],c["camera_board_width_mm"],w=w,thickness=c["camera_board_thickness_mm"])
    for u in (-14.,14.):
        for v in (-14.,14.):pcb=pcb.cut(camera_cylinder(c,u,v,w-.1,1.15,c["camera_board_thickness_mm"]+.2))
    lens=camera_cylinder(c,0,0,w+c["camera_board_thickness_mm"],c["camera_lens_radius_mm"],c["camera_lens_length_mm"])
    # Back-side keepout fits in the central aperture; reserve no named USB socket.
    back = camera_rect(c,20,20,w=w-3,thickness=3)
    return {"ASSUMED_camera_pcb":pcb,"ASSUMED_lens_envelope":lens,"ASSUMED_back_electronics":back}


@dataclass
class Item:
    key: str
    original_path: str
    shape: cq.Shape
    loc: cq.Location  # world location
    unit: str
    role: str
    color: tuple

    @property
    def world(self):return self.shape.moved(self.loc)


def physical_unit(path):
    for i,seg in enumerate(path.split('/')):
        if seg.startswith(('XL,XC-330 v1:','XL-430_new v1:')):
            return '/'.join(path.split('/')[:i+1])
    return path


@dataclass
class Design:
    config: dict
    baseline: object
    hand_world: cq.Location
    static_source_location: cq.Location
    parts: dict
    proxies: dict
    items: list[Item]
    static_index: int
    moving_index: int

    def at_opening(self, opening: float) -> list[Item]:
        if not math.isfinite(opening) or not 0 <= opening <= self.config['opening_max_deg']:
            raise ValueError('Opening outside the reviewed interval')
        turn = self.hand_world * rotate_about(PIVOT,(0,0,1),-opening) * self.hand_world.inverse
        return [Item(i.key,i.original_path,i.shape,turn*i.loc if i.role=='rotor' else i.loc,i.unit,i.role,i.color) for i in self.items]

    def in_hand(self, items):
        return [Item(i.key,i.original_path,i.shape,self.hand_world.inverse*i.loc,i.unit,i.role,i.color) for i in items]


def build(c=None):
    c=c or load_config()
    baseline=build_geometry(REPO/'hardware/follower/step')
    static=unique_occurrence(baseline.original,'/gripper v9:1/static side:1')
    moving=unique_occurrence(baseline.original,'/gripper v9:1/moving side:1')
    S=baseline.revised_locations[static.index]
    H = S*rotate_about(MOUNT_CENTER,(0,1,0),c['clocking_deg'])*cq.Location((0,c['flange_thickness_mm'],0))
    change=H*S.inverse
    parts,proxies=make_parts(c),camera_proxies(c)
    items=[]
    for row in baseline.original:
        shape=baseline.revised_shapes[row.index]
        loc=baseline.revised_locations[row.index]
        gripper='/gripper v9:1/' in row.path
        if gripper:loc=change*loc
        rotor=gripper and (row.index==moving.index or row.path.endswith((
            '/DC15_A01_HORN_DUMMY:1','/DC15_A01_HORN_IDLE2_DUMMY:1')))
        role='rotor' if rotor else ('gripper' if gripper else 'upstream')
        color = (.31,.69,.32) if row.index==static.index else ((.28,.55,.79) if row.index==moving.index else (.27,.29,.32))
        if row.index in (baseline.target_index,baseline.base_index,baseline.wrist_index):color=(.50,.56,.60)
        items.append(Item(f'original_{row.index:03d}',row.path,shape,loc,physical_unit(row.path),role,color))
    for n,s in parts.items():items.append(Item(n,n,s,H,n,'camera_mount',(.90,.54,.16) if n=='wrist_camera_bridge' else (.72,.77,.82)))
    for n,s in proxies.items():items.append(Item(n,n,s,H,'ASSUMED_CAMERA','camera_proxy',(.17,.41,.34) if 'pcb' in n else (.14,.17,.21)))
    return Design(c,baseline,H,S,parts,proxies,items,static.index,moving.index)


def assembly(items, name):
    a=cq.Assembly(name=name)
    for i in items:a.add(i.shape,loc=i.loc,name=i.key,color=cq.Color(*i.color))
    return a


def hand_items(d, opening):
    return d.in_hand([i for i in d.at_opening(opening)
                    if i.role!='upstream' or any(x in i.original_path for x in (
                        '/XL,XC-330 v1:6/','/servo connector angle v4:1/','/XL,XC-330 v1:8/'))])
