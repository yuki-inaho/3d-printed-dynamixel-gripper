import cadquery as cq
import pytest

from scripts.assembly_io import bounds, read_step
from scripts.review_pg3_drive_screw_exchange import (
    axial_bolt_path_bound,
    exchange_stages,
    supplemented_path,
)
from scripts.review_pg3_local_contacts import reexpress, review_local_pairs
from scripts.review_pg3_temporary_drive_screws import candidate


@pytest.fixture(scope="module")
def shapes():
    return {
        r.name: r.world
        for r in read_step("outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step")[2]
    }


def test_eight_paths_retain_installed_links_and_other_screw(shapes):
    stages = exchange_stages(shapes)
    assert list(stages) == [
        "bench_R_bolt",
        "bench_L_bolt",
        "R_remove_temporary",
        "R_add_washer",
        "R_add_final_bolt",
        "L_remove_temporary",
        "L_add_washer",
        "L_add_final_bolt",
    ]
    assert [len(v[1]) for v in stages.values()] == [4, 5, 259, 259, 260, 260, 260, 261]
    for name, (movers, obstacles, action) in stages.items():
        assert len(movers) == 1 and not set(movers) & set(obstacles)
        if not name.startswith("bench_"):
            assert {n for n in shapes if n.startswith("ARM_")} <= set(obstacles)
            assert {"PG3_link_R", "PG3_link_L", "PG3_XL430_fixed", "PG3_XL430_horn"} <= set(
                obstacles
            )
        assert action == ("remove" if "remove" in name else "insert")
    for side in ("R", "L"):
        name = f"PG3_pivot_drive_{side}_bolt"
        assert stages[f"bench_{side}_bolt"][0][name] is stages[f"{side}_remove_temporary"][0][name]
        assert stages[f"{side}_add_final_bolt"][0][name] is shapes[name]
        washer = f"PG3_pivot_drive_{side}_washer"
        assert stages[f"{side}_add_washer"][0][washer] is shapes[washer]
    assert (
        stages["L_remove_temporary"][1]["PG3_pivot_drive_R_bolt"]
        is shapes["PG3_pivot_drive_R_bolt"]
    )
    assert (
        stages["R_remove_temporary"][1]["PG3_pivot_drive_L_bolt"]
        is stages["bench_L_bolt"][0]["PG3_pivot_drive_L_bolt"]
    )


def test_omitted_installed_arm_is_rejected(shapes, monkeypatch):
    prepared = candidate(shapes)
    del prepared["stages"]["G4_L_link"][1]["ARM_P06_PG3_support"]
    monkeypatch.setattr("scripts.review_pg3_drive_screw_exchange.candidate", lambda *a: prepared)
    with pytest.raises(ValueError, match="complete temporary installation"):
        exchange_stages(shapes)


@pytest.mark.parametrize("side", ["R", "L"])
def test_complete_cylinder_path_bound_and_intrusive_head_negative(shapes, side):
    bolt = candidate(shapes)["temporary_screws"][f"PG3_pivot_drive_{side}_bolt"]
    host = shapes["PG3_crank"]
    proof = axial_bolt_path_bound(bolt, host)
    assert proof["status"] == "BOUNDED_TRANSLATION"
    assert 0 < proof["continuous_volume_upper_bound_mm3"] < 1e-4
    assert all(len(c["whole_obstacle_faces"]) == len(host.Faces()) for c in proof["components"])
    assert proof["components"][0]["radial_void_lower_bound_mm"] == pytest.approx(1.15, abs=2e-7)
    bad = bolt.translate((-0.2, 0, 0))
    assert axial_bolt_path_bound(bad, host)["status"] == "UNPROVEN"
    sample = review_local_pairs({"bolt": bad, "host": host}, [("bolt", "host")], 90)
    assert sample["pairs"][0]["status"] == "FAIL"
    assert sample["pairs"][0]["volume_mm3"] > 0.1


def test_radial_axis_misalignment_and_blind_bore_cannot_pass(shapes):
    bolt = candidate(shapes)["temporary_screws"]["PG3_pivot_drive_R_bolt"]
    host = shapes["PG3_crank"]
    assert axial_bolt_path_bound(bolt.translate((0, 0.2, 0)), host)["status"] == "UNPROVEN"
    base = cq.Solid.makeCylinder(4, 5, (20, 248.9, 164.6), (1, 0, 0))
    through = base.cut(cq.Solid.makeCylinder(1.15, 5, (20, 248.9, 164.6), (1, 0, 0)))
    blind = base.cut(cq.Solid.makeCylinder(1.15, 4.5, (20.5, 248.9, 164.6), (1, 0, 0)))
    assert axial_bolt_path_bound(bolt, through)["status"] == "BOUNDED_TRANSLATION"
    proof = axial_bolt_path_bound(bolt, blind)
    assert proof["status"] == "UNPROVEN"
    assert proof["components"][0]["radial_void_lower_bound_mm"] == 0
    sample = review_local_pairs({"bolt": bolt, "blind": blind}, [("bolt", "blind")], 90)
    assert sample["pairs"][0]["status"] == "FAIL"


def test_whole_bolt_bulge_outside_two_cylinder_cover_is_rejected(shapes):
    bolt = candidate(shapes)["temporary_screws"]["PG3_pivot_drive_R_bolt"]
    # Keep one intact identifiable head cylinder so the containment check is exercised.
    bulged = bolt.fuse(cq.Solid.makeCylinder(3, 0.5, (31.5, 248.9, 164.6), (1, 0, 0)))
    proof = axial_bolt_path_bound(bulged, shapes["PG3_crank"])
    assert proof["status"] == "UNPROVEN"
    assert not proof["whole_bolt_containment"]["pass"]


@pytest.mark.parametrize("travel", [0, -60, float("nan"), float("inf")])
def test_unsupported_travel_cannot_become_zero_path(shapes, travel):
    with pytest.raises(ValueError, match="finite positive"):
        axial_bolt_path_bound(shapes["PG3_pivot_drive_R_bolt"], shapes["PG3_crank"], travel)


def test_common_rigid_frame_maps_all_positive_x_offsets_to_positive_z(shapes):
    for name in ("PG3_pivot_drive_R_bolt", "PG3_crank", "PG3_pivot_drive_R_washer"):
        first = reexpress(shapes[name].translate((60, 0, 0)), 90)
        second = reexpress(shapes[name], 90).translate((0, 0, 60))
        assert bounds(first) == pytest.approx(bounds(second), abs=1e-6)


def test_any_real_sample_failure_overrides_a_supplemental_clear_bound(monkeypatch):
    box = cq.Solid.makeBox(1, 1, 1)
    good = {"far_pairs": [["m", "o"]], "near_pairs": [], "actual_penetration_samples": []}
    bad = good | {"actual_penetration_samples": [{"volume_mm3": 1}]}
    reports = iter((bad, good))
    monkeypatch.setattr(
        "scripts.review_pg3_drive_screw_exchange.review_stage", lambda *a: next(reports)
    )
    result = supplemented_path({"m": box}, {"o": box.translate((3, 0, 0))})
    assert result["summed_upper_bound_mm3"] == 0
    assert not result["supplemented_material_path_clear"]


def test_small_per_pair_bounds_must_not_multiply_the_total_allowance(monkeypatch):
    box = cq.Solid.makeBox(1, 1, 1)
    proof = {
        "far_pairs": [],
        "near_pairs": [
            {"a": "m", "b": name, "selected_volume_upper_bound_mm3": 0.75e-4} for name in ("a", "b")
        ],
        "actual_penetration_samples": [],
    }
    monkeypatch.setattr("scripts.review_pg3_drive_screw_exchange.review_stage", lambda *a: proof)
    result = supplemented_path({"m": box}, {"a": box, "b": box.translate((3, 0, 0))})
    assert result["summed_upper_bound_mm3"] == pytest.approx(1.5e-4)
    assert not result["supplemented_material_path_clear"]
