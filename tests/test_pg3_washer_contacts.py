import math

import cadquery as cq
import pytest

import scripts.review_pg3_washer_contacts as checker
from gripper_design.pg3 import PG3Model, to_arm
from scripts.review_pg3_washer_contacts import finite_solid, inspect_washer_contact, opposed_seat


@pytest.fixture(scope="module")
def shapes():
    return {n: to_arm(s) for n, s in PG3Model().neutral.items()}


def test_washer_pushed_into_shoulder_is_not_seating(shapes):
    report = inspect_washer_contact(
        shapes["crank"],
        shapes["pivot_drive_L_bolt"],
        shapes["pivot_drive_L_washer"].translate((-0.2, 0, 0)),
        "L",
        90,
    )
    assert not report["nominal_contact_pass"]


@pytest.mark.parametrize("side,angle", [("L", 25), ("L", 90), ("R", 90), ("R", 135)])
def test_complete_nominal_contacts_remain_seated(side, angle):
    shapes = {n: to_arm(s) for n, s in PG3Model().at(angle).items()}
    report = inspect_washer_contact(
        shapes["crank"],
        shapes[f"pivot_drive_{side}_bolt"],
        shapes[f"pivot_drive_{side}_washer"],
        side,
        angle,
    )
    assert report["nominal_contact_pass"], report
    assert report["status"] == "NOMINAL_CONTACT"
    assert report["shoulder_contact"]["common_area_mm2"] == pytest.approx(
        math.pi * (2.5**2 - 1.15**2)
    )
    assert report["head_contact"]["common_area_mm2"] == pytest.approx(math.pi * (1.9**2 - 1.1**2))
    assert report["shank_to_bore_radial_gap_mm"] == pytest.approx(0.1)
    assert not report["installation_approved"]
    assert not report["physical_free_motion_verified"]


def test_missing_annular_material_does_not_inherit_round_symmetry(shapes):
    washer = shapes["pivot_drive_L_washer"]
    notch = cq.Solid.makeBox(1, 1, 1, (29.4, 223.5, 164))
    changed = washer.cut(notch)
    assert changed.isValid() and changed.Volume() < washer.Volume() - 0.1
    report = inspect_washer_contact(shapes["crank"], shapes["pivot_drive_L_bolt"], changed, "L", 90)
    assert not report["nominal_contact_pass"]


def test_extra_bolt_material_inside_washer_not_waived(shapes):
    washer, bolt = shapes["pivot_drive_L_washer"], shapes["pivot_drive_L_bolt"]
    extra = cq.Solid.makeCylinder(1.3, 0.2, (29.7, 220.9, 164.6), (1, 0, 0))
    changed = bolt.fuse(extra)
    assert changed.isValid() and len(changed.Solids()) == 1
    assert changed.intersect(washer).Volume() > 0.1
    report = inspect_washer_contact(shapes["crank"], changed, washer, "L", 90)
    assert not report["nominal_contact_pass"]


def test_matching_same_facing_seats_are_not_contact():
    first = cq.Solid.makeCylinder(2, 1, (0, 0, 0), (1, 0, 0))
    result = opposed_seat(first, first.copy(), 1, 4 * math.pi)
    assert result["common_area_mm2"] > 12
    assert not result["pass_contact"]


def test_inverted_finite_solid_rejected(shapes):
    washer = shapes["pivot_drive_L_washer"].copy()
    washer.wrapped.Reverse()
    with pytest.raises(ValueError, match="outward"):
        finite_solid(washer)


def test_failed_boolean_evidence_is_not_a_successful_negative(shapes, monkeypatch):
    def failed(*args, **kwargs):
        raise checker.EvidenceError("containment self-control failed")

    monkeypatch.setattr(checker, "controlled_containment", failed)
    result = inspect_washer_contact(
        shapes["crank"], shapes["pivot_drive_L_bolt"], shapes["pivot_drive_L_washer"], "L", 90
    )
    assert result["status"] == "ERROR"
    assert not result["nominal_contact_pass"]


def test_nan_self_common_is_not_accepted(shapes, monkeypatch):
    class InvalidCommon:
        def isValid(self):
            return True

        def Volume(self):
            return math.nan

    monkeypatch.setattr(cq.Shape, "intersect", lambda *args, **kwargs: InvalidCommon())
    washer = shapes["pivot_drive_L_washer"]
    with pytest.raises(checker.EvidenceError, match="self-control"):
        checker.controlled_containment(washer, washer.copy(), equal=True)


@pytest.mark.parametrize("part,shift", [("washer", (0, 0.2, 0)), ("bolt", (-0.2, 0, 0))])
def test_axis_and_seat_displacements_are_not_nominal(shapes, part, shift):
    bolt, washer = shapes["pivot_drive_L_bolt"], shapes["pivot_drive_L_washer"]
    if part == "washer":
        washer = washer.translate(shift)
    else:
        bolt = bolt.translate(shift)
    assert not inspect_washer_contact(shapes["crank"], bolt, washer, "L", 90)[
        "nominal_contact_pass"
    ]
