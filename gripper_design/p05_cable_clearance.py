"""Wider V2 P05 windows preserving the actual nominal motor seating faces.

This separate candidate does not approve harness bends, prewired motor insertion,
print tolerances or fabrication. The earlier 3x8 mm variant stays unchanged.
"""

import math
from dataclasses import asdict, dataclass
from pathlib import Path

import cadquery as cq

from gripper_design.p05_cable_relief import SIDE_WALLS_X_MM, protected
from scripts.assembly_io import bounds

DEFAULT_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "studies/low-profile-20260926/outputs/low-profile-250g/CAD/final-version.step"
)
SOURCE_SHA256 = "9f58c947753e9229b30939da23ce4c87c1cc85eeb39372518de4ffb98991b93f"
VOLUME_TOLERANCE_MM3 = 1e-4
AREA_TOLERANCE_MM2 = 1e-4


@dataclass(frozen=True)
class WindowSpec:
    width_mm: float = 5.5
    height_mm: float = 10.2
    corner_radius_mm: float = 0.5
    centre_y_mm: float = 151.15
    centre_z_mm: float = 178.7

    def validate(self):
        if not all(math.isfinite(v) for v in asdict(self).values()):
            raise ValueError("window dimensions must be finite")
        if min(self.width_mm, self.height_mm, self.corner_radius_mm) <= 0:
            raise ValueError("window dimensions must be positive")
        if 2 * self.corner_radius_mm >= min(self.width_mm, self.height_mm):
            raise ValueError("corner radius must be smaller than half the window")


def volume(shape):
    return sum(abs(s.Volume()) for s in shape.Solids())


def area(shape):
    return sum(abs(f.Area()) for f in shape.Faces())


DEFAULT_WINDOW = WindowSpec()


def change_mask(spec=DEFAULT_WINDOW):
    """Two rounded rectangle cuts, confined to the original side walls."""
    spec.validate()
    masks = []
    for lo, hi in SIDE_WALLS_X_MM:
        masks.append(
            cq.Workplane("YZ", origin=(lo - 1, spec.centre_y_mm, spec.centre_z_mm))
            .rect(spec.width_mm, spec.height_mm)
            .extrude(hi - lo + 2)
            .edges("|X")
            .fillet(spec.corner_radius_mm)
            .val()
        )
    return cq.Compound.makeCompound(masks)


def _x_faces(shape, x):
    return [
        f
        for f in shape.Faces()
        if f.geomType() == "PLANE" and abs(bounds(f)[0] - x) < 1e-6 and abs(bounds(f)[3] - x) < 1e-6
    ]


def _face_control(face):
    copied = face.copy()
    return (
        face.isValid()
        and area(face.cut(copied)) < AREA_TOLERANCE_MM2
        and abs(area(face.intersect(copied)) - face.Area()) < AREA_TOLERANCE_MM2
    )


def _contact(p05, cases, x):
    support = _x_faces(p05, x)
    if len(support) != 1:
        raise ValueError("expected one P05 inner seating plane per side")
    face = support[0]
    patches, normal_dots = [], []
    if not _face_control(face):
        raise ValueError("P05 seat Boolean control failed")
    for case in cases:
        for case_face in _x_faces(case, x):
            if not _face_control(case_face):
                raise ValueError("motor seat Boolean control failed")
            common = face.intersect(case_face)
            if not common.isValid():
                raise ValueError("invalid contact patch")
            if area(common) > AREA_TOLERANCE_MM2:
                patches.extend(common.Faces())
                normal_dots.append(face.normalAt().dot(case_face.normalAt()))
    if not patches or any(abs(dot + 1) > 1e-6 for dot in normal_dots):
        raise ValueError("expected opposed material seating faces")
    return cq.Compound.makeCompound(patches), normal_dots


def seat_preservation(before, after, cases):
    """Compare actual trimmed opposed contact sets, not bounding-box width."""
    records = []
    for x in (-14.45, 14.05):
        old, normal_dots = _contact(before, cases, x)
        new, _ = _contact(after, cases, x)
        lost, added = area(old.cut(new)), area(new.cut(old))
        records.append(
            {
                "x_mm": x,
                "before_mm2": area(old),
                "after_mm2": area(new),
                "lost_mm2": lost,
                "added_mm2": added,
                "normal_dot": min(normal_dots),
                "passed": lost < AREA_TOLERANCE_MM2 and added < AREA_TOLERANCE_MM2,
            }
        )
    return records


def candidate(source, cases, spec=DEFAULT_WINDOW):
    if not source.isValid() or len(source.Solids()) != 1 or volume(source) <= 0:
        raise ValueError("P05 source must be a valid single solid")
    mask = change_mask(spec)
    if volume(source.intersect(mask).intersect(protected())) > VOLUME_TOLERANCE_MM3:
        raise ValueError("window enters protected screw or bridge material")
    new = source.cut(mask)
    if not new.isValid() or len(new.Solids()) != 1 or volume(new) <= 0:
        raise ValueError("window leaves invalid or disconnected support")
    removed = source.cut(new)
    if volume(removed.cut(mask)) > VOLUME_TOLERANCE_MM3:
        raise ValueError("change extends outside declared mask")
    if volume(new.cut(source)) > VOLUME_TOLERANCE_MM3:
        raise ValueError("candidate unexpectedly adds material")
    if not all(r["passed"] for r in seat_preservation(source, new, cases)):
        raise ValueError("window removes actual case seating material")
    return new


def nominal_plug_corridors(spec=DEFAULT_WINDOW):
    """JST EHR-3 housing envelope swept through P05 BEFORE motor insertion.

    Housing width9.5 is oriented along Z, thickness3.8 along Y. The axial
    6.5+0.6 mm allowance only defines this conservative local sweep; this is
    neither actual plug CAD nor connector access with the motor installed.
    """
    spec.validate()
    result = {}
    for i, (lo, hi) in enumerate(SIDE_WALLS_X_MM):
        result[f"PLUG_WINDOW_ONLY_{i}"] = cq.Solid.makeBox(
            hi - lo + 2 * 7.1,
            3.8,
            9.5,
            (lo - 7.1, spec.centre_y_mm - 1.9, spec.centre_z_mm - 4.75),
        )
    return result
