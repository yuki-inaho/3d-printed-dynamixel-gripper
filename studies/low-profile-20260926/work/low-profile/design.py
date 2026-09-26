"""Local finger stretch, keeping all source geometry behind the declared plane."""

import math
import sys
from pathlib import Path

import cadquery as cq

sys.path.insert(0, "/home/inaho-omen/Project/3d-printed-dynamixel-gripper")
from gripper_design.camera_overhead_r4 import box
from scripts.assembly_io import read_step

REPO = Path("/home/inaho-omen/Project/3d-printed-dynamixel-gripper")
SOURCE = (
    REPO / "outputs/camera-mount-id5-overhead-d405-r5/CAD/ID5_D405_mid_ASSEMBLY.step"
)
CUT_Y = 203.6
TOL_VOLUME = 1e-5
G = 9.80665


def load_source():
    rows = read_step(SOURCE)[2]
    assert len(rows) == len({r.name for r in rows}) == 257
    return {r.name: r.world for r in rows if not r.name.startswith("CAM5_")}


def length_check(delta):
    if not math.isfinite(delta) or not 0 <= delta <= 30:
        raise ValueError("Extension outside declared finite 0..30 mm range")


def mask(y0, y1):
    return box(-100, 100, y0, y1, 100, 250)


def extend_finger(shape, delta):
    length_check(delta)
    if delta == 0:
        return shape
    root = shape.intersect(mask(100, CUT_Y))
    tip = shape.intersect(mask(CUT_Y, 300)).translate((0, delta, 0))
    faces = [
        f
        for f in root.Faces()
        if f.geomType() == "PLANE"
        and abs(f.Center().y - CUT_Y) < 1e-6
        and f.normalAt().y > 0.999
    ]
    if not faces:
        raise ValueError("No forward section face at declared cut plane")
    bridges = [
        cq.Solid.extrudeLinear(f.outerWire(), f.innerWires(), cq.Vector(0, delta, 0))
        for f in faces
    ]
    result = root.fuse(*bridges, tip).clean()
    if not result.isValid() or len(result.Solids()) != 1:
        raise ValueError("Extension is not one valid connected solid")
    return result


def extended_arm(arm, delta):
    length_check(delta)
    result = dict(arm)
    for side in ["L", "R"]:
        name = f"PG3_finger_{side}"
        result[name] = extend_finger(arm[name], delta)
        name = f"PG3_pad_{side}"
        result[name] = arm[name].translate((0, delta, 0))
    return result


def symmetric_difference(a, b):
    """Volume equality control prevents kernel failure becoming zero difference."""
    for shape in [a, b]:
        own_volume = abs(shape.Volume())
        if not shape.isValid() or not shape.Solids() or own_volume < TOL_VOLUME:
            raise ValueError("Invalid/empty comparison operand")
        if abs(abs(shape.intersect(shape).Volume()) - own_volume) > TOL_VOLUME:
            raise ValueError("Boolean self-intersection control failed")
        if abs(shape.cut(shape).Volume()) > TOL_VOLUME:
            raise ValueError("Boolean self-difference control failed")
    return abs(a.cut(b).Volume()) + abs(b.cut(a).Volume())


def preservation(old, new, delta):
    length_check(delta)
    report = {"valid": new.isValid(), "solid_count": len(new.Solids())}
    if not report["valid"] or report["solid_count"] != 1:
        return report | {"pass": False}
    if new.BoundingBox().ymin >= CUT_Y:
        return report | {
            "pass": False,
            "reason": "whole new solid is outside the preserved root region",
        }
    root_mask = mask(100, CUT_Y)
    tip_mask = mask(CUT_Y + delta + 1e-4, 350)
    root_diff = symmetric_difference(old.intersect(root_mask), new.intersect(root_mask))
    expected_tip = old.translate((0, delta, 0)).intersect(tip_mask)
    actual_tip = new.intersect(tip_mask)
    tip_diff = symmetric_difference(expected_tip, actual_tip)
    return report | {
        "root_difference_mm3": root_diff,
        "tip_difference_mm3": tip_diff,
        "pass": root_diff < TOL_VOLUME and tip_diff < TOL_VOLUME,
    }


def payload_delta(delta):
    length_check(delta)
    return 0.25 * G * delta / 1000
