"""Local finger stretch, keeping all source geometry behind the declared plane."""

import math
import sys

import cadquery as cq
from paths import REPO

sys.path.insert(0, str(REPO))
from gripper_design.camera_overhead_r4 import box
from scripts.assembly_io import read_step

SOURCE = REPO / "outputs/camera-mount-id5-overhead-d405-r5/CAD/ID5_D405_mid_ASSEMBLY.step"
CUT_Y = 203.6
TOL_VOLUME = 1e-5
G = 9.80665


def load_source():
    rows = read_step(SOURCE)[2]
    if len(rows) != 257 or len({r.name for r in rows}) != 257:
        raise ValueError("Expected all 257 uniquely named R5 occurrences")
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
        if f.geomType() == "PLANE" and abs(f.Center().y - CUT_Y) < 1e-6 and f.normalAt().y > 0.999
    ]
    if not faces:
        raise ValueError("No forward section face at declared cut plane")
    bridges = [
        cq.Solid.extrudeLinear(f.outerWire(), f.innerWires(), cq.Vector(0, delta, 0)) for f in faces
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
    """Reject unreliable no-op Booleans on independent geometric copies."""

    def volume(shape):
        values = [solid.Volume() for solid in shape.Solids()]
        if (
            not shape.isValid()
            or any(not math.isfinite(v) or v <= 0 for v in values)
            or (not values and shape.Faces())
        ):
            raise ValueError("Invalid Boolean result")
        return sum(values)

    for shape in (a, b):
        own_volume = volume(shape)
        if own_volume < TOL_VOLUME:
            raise ValueError("Invalid/empty comparison operand")
        # CadQuery copy() uses BRepBuilderAPI_Copy with copyGeom=True.
        independent = shape.copy()
        if abs(volume(independent) - own_volume) > TOL_VOLUME:
            raise ValueError("Independent copy changed the operand")
        for left, right in ((shape, independent), (independent, shape)):
            if abs(volume(left.intersect(right)) - own_volume) > TOL_VOLUME:
                raise ValueError("Independent Boolean intersection control failed")
            if volume(left.cut(right)) > TOL_VOLUME:
                raise ValueError("Independent Boolean difference control failed")
    return volume(a.cut(b)) + volume(b.cut(a))


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
