import math

import cadquery as cq
import numpy as np
import pytest

from gripper_design.interface_envelopes import axial_ray_cover
from gripper_design.pg3 import PG3Model, group_transform, position_mm, to_arm
from scripts.review_pg3_motion_clearance import DistanceTo
from scripts.review_pg3_pivot_motion import (
    inspect_pivot_motion,
    moved,
    neutral,
    relative_to_link,
    verified_link_voids,
)


def test_face_ray_cover_includes_body_interior_not_only_boundary():
    source = cq.Solid.makeBox(10, 10, 10)
    pieces, evidence = axial_ray_cover(source)
    assert len(pieces) == len(source.Faces())
    assert len(evidence["all_boundary_faces"]) == len(source.Faces())
    interior = cq.Solid.makeBox(1, 1, 1, (4, 4, 4))
    assert any(s.intersect(interior).Volume() > 0.99 for s in pieces.values())


def test_ray_cover_keeps_curved_extrema_and_rejects_shell_only():
    source = cq.Solid.makeCylinder(2, 4, (0, 0, 0), (1, 0, 0))
    pieces, _ = axial_ray_cover(source)
    inside = cq.Solid.makeBox(0.2, 0.2, 0.2, (1, -0.1, 1.5))
    assert any(p.intersect(inside).Volume() > 0.0079 for p in pieces.values())
    with pytest.raises(ValueError, match="solid"):
        axial_ray_cover(source.Shells()[0])


def test_ray_cover_rejects_inverted_unbounded_solid():
    box = cq.Solid.makeBox(5, 5, 5)
    inverted = cq.Shape.cast(box.wrapped.Reversed())
    assert inverted.isValid()
    with pytest.raises(ValueError, match="bounded"):
        axial_ray_cover(inverted)


@pytest.fixture(scope="module")
def source_parts():
    return {n: to_arm(s) for n, s in PG3Model().neutral.items()}


@pytest.mark.parametrize("side", ["L", "R"])
def test_link_frame_distance_equals_world_distance(source_parts, side):
    """The certifier measures in the link frame; the world-frame answer must agree."""
    local_link = neutral(source_parts[f"link_{side}"])
    to_link = DistanceTo(local_link)
    for host_name, group in ((f"carriage_{side}", side), ("crank", "drive")):
        local = neutral(source_parts[host_name])
        for degrees in (25, 47.5, 90, 112.5, 135):
            t = math.radians(degrees)
            world = moved(local, group, t).distance(moved(local_link, f"link_{side}", t))
            relative = to_link(relative_to_link(local, group, f"link_{side}", t))
            assert relative == pytest.approx(world, abs=1e-9), (host_name, degrees)


@pytest.mark.parametrize(
    "side,kind", [("L", "drive"), ("R", "drive"), ("L", "carriage"), ("R", "carriage")]
)
def test_whole_host_link_motion_includes_every_face(source_parts, side, kind):
    host = source_parts["crank" if kind == "drive" else f"carriage_{side}"]
    result = inspect_pivot_motion(host, source_parts[f"link_{side}"], side, kind)
    assert result["status"] == "PROVEN_CLEAR", result["cover_checks"]
    assert len(result["cover_checks"]) == len(host.Faces())
    assert result["all_source_faces_covered"]
    assert any(
        r["method"] == "verified_void_and_corresponding_pivot_trajectories"
        for r in result["cover_checks"]
    )


def test_link_void_does_not_accept_a_plug(source_parts):
    link = source_parts["link_L"]
    bore = verified_link_voids(link)[0]
    y, z = bore["axis_yz_mm"]
    plug = cq.Solid.makeCylinder(3.0, 0.2, (27, y, z), (1, 0, 0))
    filled = link.fuse(plug)
    assert filled.isValid() and len(filled.Solids()) == 1
    with pytest.raises(ValueError):
        verified_link_voids(filled)


@pytest.mark.parametrize("side", ["L", "R"])
def test_both_link_endpoints_follow_the_host_pivots(side):
    sign = 1 if side == "R" else -1
    pin = np.array([0, sign * 14, 0, 1])
    slider = np.array([sign * position_mm(90), 0, 0, 1])
    for angle in np.linspace(25, 135, 25):
        link_motion = group_transform(f"link_{side}", angle)
        assert link_motion @ pin == pytest.approx(group_transform("drive", angle) @ pin, abs=1e-10)
        assert link_motion @ slider == pytest.approx(
            group_transform(side, angle) @ slider, abs=1e-10
        )
        assert math.dist((link_motion @ pin)[:3], (link_motion @ slider)[:3]) == pytest.approx(24)


def test_off_axis_pin_is_not_waived_as_a_mating_contact(source_parts):
    host = source_parts["crank"].translate((0, 0.3, 0))
    result = inspect_pivot_motion(host, source_parts["link_L"], "L", "drive")
    assert result["status"] == "UNPROVEN"


def test_extra_material_outside_pivot_hole_is_not_waived(source_parts):
    link = source_parts["link_L"]
    host = source_parts["carriage_L"].fuse(link.translate((-1, 0, 0)))
    assert host.isValid() and len(host.Solids()) == 1
    assert host.distance(link) == pytest.approx(0, abs=1e-7)
    result = inspect_pivot_motion(host, link, "L", "carriage")
    assert result["status"] == "UNPROVEN"
    assert result["all_source_faces_covered"]
