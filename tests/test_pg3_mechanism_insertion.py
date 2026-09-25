import cadquery as cq
import pytest

from scripts.review_pg3_mechanism_insertion import (
    aabb_overlap_upper,
    axial_boss_insertion_certificate,
    distance_certificate,
    enclosure_bounds,
    insertion_stages,
    review_stage,
    split_stage,
    swept_bounds,
)
from scripts.step_cache import read_rows


def test_body_insertion_partition_excludes_only_movers_and_later_screws():
    before = {"arm": object(), "motor": object()}
    after = before | {"frame": object(), "nut": object(), "screw": object()}
    movers, obstacles, later = split_stage(before, after, {"screw"})
    assert set(movers) == {"frame", "nut"}
    assert set(obstacles) == {"arm", "motor"}
    assert later == {"screw"}
    assert not set(movers) & set(obstacles)


def test_no_previous_part_disappears_or_is_replaced():
    old = object()
    with pytest.raises(ValueError):
        split_stage({"old": old}, {"new": object()}, set())
    with pytest.raises(ValueError):
        split_stage({"old": old}, {"old": object(), "new": object()}, set())
    with pytest.raises(ValueError):
        split_stage({"old": old}, {"old": old, "new": object()}, {"old"})


def test_saved_stage_coverage_and_post_insertion_screws():
    shapes = {
        r.name: r.world
        for r in read_rows("outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step")
    }
    stages = insertion_stages(shapes)
    g1, g2 = stages["G1_frame_case"], stages["G2_horn_drive"]
    assert len(g1[0]) == 5
    assert g1[2] == {"PG3_case_tapper_-11", "PG3_case_tapper_11"}
    assert set(g2[0]) == {
        "PG3_horn_spacer",
        "PG3_crank",
        "PG3_pivot_drive_L_nut",
        "PG3_pivot_drive_R_nut",
    }
    assert g2[2] == {f"PG3_horn_bolt_{i}" for i in range(4)}
    assert set(g2[1]) == set(g1[1]) | set(g1[0]) | g1[2]
    assert set(g1[1]) == {n for n in shapes if n.startswith("ARM_")} | {
        "PG3_XL430_fixed",
        "PG3_XL430_horn",
    }


def test_intermediate_intrusion_does_not_inherit_clear_endpoints():
    mover = cq.Solid.makeBox(0.1, 1, 1)
    obstacle = cq.Solid.makeBox(0.02, 1, 1, (0.52, 0, 0))
    assert mover.intersect(obstacle).Volume() == 0
    assert mover.translate((1, 0, 0)).intersect(obstacle).Volume() == 0
    r = review_stage({"body": mover}, {"obstacle": obstacle}, (1, 0, 0))
    assert not r["continuous_translation_volume_clear"]
    assert r["actual_penetration_samples"][0]["fraction"] == 0.5
    assert r["pair_count"] == 1


def test_full_cartesian_pair_coverage_and_far_path():
    cube = cq.Solid.makeBox(1, 1, 1)
    r = review_stage(
        {"a": cube, "b": cube.translate((2, 0, 0))},
        {"wall": cube.translate((0, 10, 0)), "upper": cube.translate((0, 0, 10))},
        (-3, 0, 0),
    )
    assert r["pair_count"] == 4
    assert len(r["far_pairs"]) == 4
    assert r["continuous_translation_volume_clear"]
    assert not r["positive_clearance_proven"]
    bb = swept_bounds(cube, (-3, 0, 0))
    assert bb == pytest.approx([-3, 0, 0, 1, 1, 1])
    with pytest.raises(ValueError):
        review_stage({"a": cube}, {"a": cube}, (1, 0, 0))
    with pytest.raises(ValueError):
        swept_bounds(cube, (float("nan"), 0, 0))


def test_cover_error_is_retained(monkeypatch):
    cube = cq.Solid.makeBox(1, 1, 1)

    def fail(*args):
        raise RuntimeError("injected kernel failure")

    monkeypatch.setattr("scripts.review_pg3_mechanism_insertion.certify_pair", fail)
    r = review_stage({"mover": cube}, {"obstacle": cube}, (1, 0, 0))
    assert not r["continuous_translation_volume_clear"]
    assert r["near_pairs"][0]["continuous_cover"]["status"] == "ERROR"


def test_whole_path_distance_bound_not_clear_endpoints():
    body = cq.Solid.makeBox(0.1, 1, 1)
    obstacle = cq.Solid.makeBox(0.01, 1, 1, (0.46, 0, 0))
    assert distance_certificate(body, obstacle, (1, 0, 0))["status"] == "UNPROVEN"
    clear = distance_certificate(body, obstacle.translate((0, 3, 0)), (1, 0, 0))
    assert clear["status"] == "PROVEN_CLEAR"
    assert clear["speed_bound_mm_per_fraction"] == 1
    with pytest.raises(ValueError):
        distance_certificate(body.Faces()[0], obstacle, (1, 0, 0))


def test_swept_box_bound_and_stage_budget_are_not_per_pair_allowances():
    assert aabb_overlap_upper([0, 0, 0, 1, 1, 1], [1, 0, 0, 2, 1, 1]) == 0
    with pytest.raises(ValueError):
        aabb_overlap_upper([0, 0, 0, float("nan"), 1, 1], [0, 0, 0, 1, 1, 1])
    body = cq.Solid.makeBox(1, 1, 1)
    wall = cq.Solid.makeBox(1, 1, 1, (1 - 7.5e-5, 0, 0))
    result = review_stage({"body": body}, {"first": wall, "second": wall.copy()}, (0, 0, 0))
    assert all(r["selected_volume_upper_bound_mm3"] < 1e-4 for r in result["near_pairs"])
    assert result["summed_overlap_upper_bound_mm3"] > 1e-4
    assert not result["continuous_translation_volume_clear"]


def test_boss_void_certificate_and_actual_penetration_controls():
    horn = cq.Solid.makeBox(4, 10, 10, (-4, -5, -5)).fuse(
        cq.Solid.makeCylinder(2, 2, (0, 0, 0), (1, 0, 0))
    )
    spacer = cq.Solid.makeCylinder(4, 1.5, (0, 0, 0), (1, 0, 0)).cut(
        cq.Solid.makeCylinder(2.3, 1.5, (0, 0, 0), (1, 0, 0))
    )
    kwargs = {"seat": 0, "centre": (0, 0), "radius": 2}
    result = axial_boss_insertion_certificate(spacer, horn, (60, 0, 0), **kwargs)
    assert result["status"] == "BOUNDED_TRANSLATION"
    assert 0 <= result["continuous_volume_upper_bound_mm3"] < 1e-4
    assert (
        result["entire_mover_axial_cylinder_check"]["whole_material_radial_gap_lower_bound_mm"]
        > 0.29
    )
    for shift in ((-0.2, 0, 0), (0, 0.5, 0)):
        moved = spacer.translate(shift)
        assert moved.intersect(horn).Volume() > 0.1
        assert (
            axial_boss_insertion_certificate(moved, horn, (60, 0, 0), **kwargs)["status"]
            == "UNPROVEN"
        )
    with pytest.raises(ValueError):
        axial_boss_insertion_certificate(spacer, horn, (-60, 0, 0), **kwargs)
    with pytest.raises(ValueError):
        axial_boss_insertion_certificate(spacer, horn, (60, 0.1, 0), **kwargs)
    plugged = spacer.fuse(cq.Solid.makeCylinder(2.5, 1.5, (0, 0, 0), (1, 0, 0)))
    assert plugged.intersect(horn).Volume() > 0.1
    assert (
        axial_boss_insertion_certificate(plugged, horn, (60, 0, 0), **kwargs)["status"]
        == "UNPROVEN"
    )


def test_saved_spacer_boss_full_shape_coverage():
    shapes = {
        r.name: r.world
        for r in read_rows("outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step")
    }
    spacer, horn = shapes["PG3_horn_spacer"], shapes["PG3_XL430_horn"]
    kwargs = {"seat": 18.8, "centre": (234.9, 164.6), "radius": 4}
    r = axial_boss_insertion_certificate(spacer, horn, (60, 0, 0), **kwargs)
    assert r["status"] == "BOUNDED_TRANSLATION"
    assert r["whole_obstacle_cover"]["source_face_count"] == len(horn.Faces())
    assert len(r["entire_mover_axial_cylinder_check"]["all_boundary_faces"]) == len(spacer.Faces())
    for shift in ((-0.2, 0, 0), (0, 0.5, 0)):
        assert (
            axial_boss_insertion_certificate(spacer.translate(shift), horn, (60, 0, 0), **kwargs)[
                "status"
            ]
            == "UNPROVEN"
        )


def test_unbounded_material_rejected_before_even_far_pair_shortcut():
    cube = cq.Solid.makeBox(1, 1, 1)
    reversed_solid = cq.Shape.cast(cube.wrapped.Reversed())
    with pytest.raises(ValueError, match="finite positive material"):
        review_stage({"mover": cube}, {"bad": reversed_solid.translate((0, 100, 0))}, (1, 0, 0))
    surface = cube.Faces()[0]
    bb = enclosure_bounds(surface)
    assert all(bb[i + 3] - bb[i] >= 2e-5 - 1e-10 for i in range(3))
