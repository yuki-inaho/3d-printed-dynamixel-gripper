import math

import cadquery as cq
import numpy as np
import pytest

from gripper_design.pg3 import PG3Model, group_transform, to_arm
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3_motion_clearance import (
    KINEMATICS_PATH,
    axial_gap_certificate,
    certify_interval,
    point_speed_bound,
    verify_axial_motion_contract,
)


def test_axial_gap_proves_clearance_without_subdivision_budget():
    verify_axial_motion_contract()
    a = cq.Solid.makeBox(2, 20, 20)
    b = cq.Solid.makeBox(2, 20, 20, (2.3, 0, 0))
    assert (
        certify_interval(lambda t: a.distance(b), 100, 0, 1, max_checks=1)["status"] == "UNPROVEN"
    )
    result = axial_gap_certificate(bounds(a), bounds(b))
    assert result is not None
    assert result["status"] == "PROVEN_CLEAR"
    assert result["continuous_distance_lower_bound_mm"] == pytest.approx(0.3)


@pytest.mark.parametrize("gap", [0, -0.1, 0.000001])
def test_axial_touch_overlap_or_sub_epsilon_is_not_certified(gap):
    a = cq.Solid.makeBox(2, 2, 2)
    b = cq.Solid.makeBox(2, 2, 2, (2 + gap, 0, 0))
    assert axial_gap_certificate(bounds(a), bounds(b)) is None


def test_axial_bounds_include_curved_extrema_not_only_vertices():
    a = cq.Solid.makeSphere(2)
    b = cq.Solid.makeBox(0.2, 0.2, 0.2, (1, 0, 0))
    assert axial_gap_certificate(bounds(a), bounds(b)) is None


@pytest.mark.parametrize("bad", [[0] * 5, [0, 0, 0, float("nan"), 1, 1], [2, 0, 0, 1, 1, 1]])
def test_invalid_axial_bounds_are_rejected(bad):
    with pytest.raises(ValueError, match="bounds"):
        axial_gap_certificate(bad, [0, 0, 0, 1, 1, 1])


def test_axial_motion_source_change_requires_new_proof(tmp_path):
    original = KINEMATICS_PATH.read_text()
    changed = original.replace(
        "tform = np.eye(4)", "tform = np.eye(4)\n    tform[2, 3] = 10 * math.sin(t)"
    )
    assert changed != original
    source = tmp_path / "axially_moving_pg3.py"
    source.write_text(changed)
    # At 90deg the modified drive translates construction Z by 10mm. Two solids
    # whose initial X projections are clear then overlap: the old proof is unsafe.
    transform = group_transform("drive", 90)
    transform[2, 3] = 10 * math.sin(math.radians(90))
    first = cq.Solid.makeBox(2, 2, 2)
    second = first.translate((0, 0, 10))
    assert axial_gap_certificate(bounds(to_arm(first)), bounds(to_arm(second))) is not None
    moved = first.translate(tuple(transform[:3, 3]))
    assert to_arm(moved).distance(to_arm(second)) == pytest.approx(0, abs=1e-7)
    with pytest.raises(ValueError, match="unreviewed PG3 kinematics"):
        verify_axial_motion_contract(source)
    assert verify_axial_motion_contract()["world_axis"] == "X"


@pytest.mark.parametrize("side", ["L", "R"])
@pytest.mark.parametrize("pivot", ["drive", "carriage"])
def test_saved_link_washer_has_invariant_axial_separation(side, pivot, tmp_path):
    verify_axial_motion_contract()
    model = PG3Model()
    names = [f"link_{side}", f"pivot_{pivot}_{side}_washer"]
    assembly = cq.Assembly()
    for name in names:
        assembly.add(to_arm(model.neutral[name]), name=name)
    path = tmp_path / "pair.step"
    assembly.save(str(path))
    saved = {r.name: r.world for r in read_step(path)[2]}
    result = axial_gap_certificate(*(bounds(saved[n]) for n in names))
    assert result is not None
    assert result["continuous_distance_lower_bound_mm"] == pytest.approx(0.3, abs=1e-7)
    # Samples corroborate the reviewed analytic invariant; they are not its proof.
    for angle in (25, 31.875, 80, 90, 135):
        moving = model.at(angle)
        assert to_arm(moving[names[0]]).distance(to_arm(moving[names[1]])) >= 0.3 - 1e-7


def test_continuous_bound_rejects_collision_between_clear_samples():
    # The endpoints and midpoint are clear, but a quarter-interval collision exists.
    distance = lambda t: max(0, abs(t - 0.25) - 0.02)
    assert all(distance(t) > 0 for t in (0, 0.5, 1))
    result = certify_interval(distance, 1.0, 0, 1, min_span=0.001)
    assert result["status"] == "UNPROVEN"
    assert certify_interval(lambda t: 2, 1, 0, 1)["status"] == "PROVEN_CLEAR"
    assert certify_interval(lambda t: 0, 0, 0, 1)["status"] == "UNPROVEN"


@pytest.mark.parametrize("speed", [-1, float("nan"), float("inf")])
def test_invalid_speed_is_not_a_certificate(speed):
    with pytest.raises(ValueError):
        certify_interval(lambda t: 2, speed, 0, 1)


def test_nonfinite_distance_and_exhausted_budget_do_not_pass():
    with pytest.raises(ValueError):
        certify_interval(lambda t: float("nan"), 1, 0, 1)
    result = certify_interval(lambda t: 0.001, 1, 0, 1, max_checks=2)
    assert result["status"] == "UNPROVEN"


@pytest.mark.parametrize(
    "group", ["fixed", "drive", "R", "L", "pin_R", "pin_L", "link_R", "link_L"]
)
def test_analytic_speed_bound_covers_rigid_motion(group):
    shape = cq.Solid.makeBox(5, 7, 3, (-3, 9, 2))
    bound = point_speed_bound(shape, group)
    points = [np.array((*v.toTuple(), 1)) for v in shape.Vertices()]
    for angle in np.linspace(25, 134.9, 100):
        a, b = group_transform(group, angle), group_transform(group, angle + 0.01)
        for p in points:
            measured = np.linalg.norm((b @ p - a @ p)[:3]) / math.radians(0.01)
            assert measured <= bound + 1e-8


def test_actual_solid_distance_includes_containment():
    outer = cq.Solid.makeBox(10, 10, 10)
    inner = cq.Solid.makeBox(2, 2, 2, (2, 2, 2))
    assert certify_interval(lambda t: outer.distance(inner), 0, 0, 1)["status"] == "UNPROVEN"


def test_rotating_solid_detects_intermediate_obstacle_and_proves_remote_clearance():
    rotor = cq.Solid.makeSphere(0.1, (10, 0, 0))
    obstacle = cq.Solid.makeSphere(0.1, (10 * math.cos(math.pi / 8), 10 * math.sin(math.pi / 8), 0))

    def distance(t):
        return rotor.rotate((0, 0, 0), (0, 0, 1), math.degrees(t)).distance(obstacle)

    assert all(distance(t) > 0.1 for t in (0, math.pi / 4, math.pi / 2))
    speed = point_speed_bound(rotor, "drive")
    assert certify_interval(distance, speed, 0, math.pi / 2)["status"] == "UNPROVEN"
    remote = cq.Solid.makeSphere(0.1, (0, 0, 5))
    result = certify_interval(
        lambda t: rotor.rotate((0, 0, 0), (0, 0, 1), math.degrees(t)).distance(remote),
        speed,
        0,
        math.pi / 2,
    )
    assert result["status"] == "PROVEN_CLEAR"


@pytest.mark.parametrize("angle", [25, 90, 135])
def test_saved_crank_distance_does_not_miss_known_overlap(angle, tmp_path):
    assembly = cq.Assembly()
    assembly.add(to_arm(PG3Model().at(angle)["crank"]), name="crank")
    path = tmp_path / "crank.step"
    assembly.save(str(path))
    crank = read_step(path)[2][0].world
    assert crank.distance(crank.copy()) <= 1e-7
    # Crank thickness is several mm: 0.1 mm axial displacement still overlaps.
    shifted = crank.translate((0.1, 0, 0))
    assert crank.distance(shifted) <= 1e-7
    result = certify_interval(lambda t: crank.distance(shifted), 0, 0, 1)
    assert result["status"] == "UNPROVEN"
