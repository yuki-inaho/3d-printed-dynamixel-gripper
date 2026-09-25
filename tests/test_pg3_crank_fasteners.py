import cadquery as cq
import pytest

from scripts.review_pg3_crank_fasteners import inspect_bolt, inspect_cylinder_region
from scripts.step_cache import read_rows


def fixture():
    host = cq.Solid.makeBox(2, 12, 12, (0, -6, -6)).cut(
        cq.Solid.makeCylinder(1.15, 2, (0, 0, 0), (1, 0, 0))
    )
    bolt = cq.Solid.makeCylinder(1, 6, (-4, 0, 0), (1, 0, 0)).fuse(
        cq.Solid.makeCylinder(1.9, 2, (2, 0, 0), (1, 0, 0))
    )
    return host, bolt


def test_actual_penetration_is_not_accepted():
    host, bolt = fixture()
    moved = bolt.translate((-0.5, 0, 0))
    assert host.intersect(moved).Volume() > 3
    result = inspect_bolt(host, moved)
    assert result["status"] == "UNPROVEN"
    assert not result["nominal_contact_pass"]


def test_nominal_fixture_has_complete_boundary_evidence():
    host, bolt = fixture()
    result = inspect_bolt(host, bolt)
    assert result["nominal_contact_pass"], result
    assert 0 < result["summed_contact_volume_upper_bound_mm3"] < 1e-4
    for row in result["boundary_checks"].values():
        assert len(row["all_boundary_faces"]) == len(host.Faces())
    assert not result["positive_clearance_proven"]
    assert not result["installation_approved"]


@pytest.fixture(scope="module")
def saved_open():
    return {
        r.name: r.world
        for r in read_rows("outputs/pg3-installable-candidate-r4/arm_camera_open_CANDIDATE.step")
    }


@pytest.mark.parametrize("index", (1, 2, 3))
def test_saved_open_supported_complete_screws(saved_open, index):
    host, bolt = saved_open["PG3_crank"], saved_open[f"PG3_horn_bolt_{index}"]
    result = inspect_bolt(host, bolt)
    assert result["nominal_contact_pass"], result
    assert result["complete_screw_containment"]["residuals_mm3"][0] == 0
    assert result["host_face_count"] == 41


def test_saved_open_unreliable_face_remains_error_not_installation_pass(saved_open):
    # This is a fail-closed regression, NOT an acceptance test for this screw.
    result = inspect_bolt(saved_open["PG3_crank"], saved_open["PG3_horn_bolt_0"])
    assert result["status"] == "ERROR"
    assert "face 5 low split: face self-control failed" in result["reason"]
    assert not result["nominal_contact_pass"]
    assert not result["installation_approved"]


def test_lateral_misalignment_rejected():
    host, bolt = fixture()
    moved = bolt.translate((0, 0.3, 0))
    assert host.intersect(moved).Volume() > 0.1
    assert inspect_bolt(host, moved)["status"] == "UNPROVEN"


def test_extra_screw_material_outside_cylinders_is_not_discarded():
    host, bolt = fixture()
    extra = bolt.fuse(cq.Solid.makeBox(1, 2, 0.5, (0, 0, 0)))
    assert host.intersect(extra).Volume() > 0.1
    result = inspect_bolt(host, extra)
    assert not result["nominal_contact_pass"]
    assert result["status"] == "UNPROVEN"


def test_extra_host_material_cannot_hide_in_bore():
    host, bolt = fixture()
    extra = host.fuse(cq.Solid.makeBox(1, 2, 0.5, (0.5, 0, 0)))
    assert extra.intersect(bolt).Volume() > 0.1
    result = inspect_bolt(extra, bolt)
    assert result["status"] == "UNPROVEN"


def test_evaluation_error_is_not_successful_rejection(monkeypatch):
    host, bolt = fixture()

    def fail(*args):
        raise ValueError("injected face failure")

    monkeypatch.setattr("scripts.review_pg3_crank_fasteners.inspect_cylinder_region", fail)
    assert inspect_bolt(host, bolt)["status"] == "ERROR"


def test_a_small_containment_loss_is_not_silently_added_to_budget(monkeypatch):
    host, bolt = fixture()
    monkeypatch.setattr(
        "scripts.review_pg3_crank_fasteners.controlled_containment",
        lambda *args: {"pass": True, "residuals_mm3": [1e-8, 0]},
    )
    assert inspect_bolt(host, bolt)["status"] == "UNPROVEN"


def test_cylinder_wholly_inside_host_is_not_clear_without_boundary_crossing():
    host = cq.Solid.makeBox(10, 10, 10, (-5, -5, -5))
    result = inspect_cylinder_region(
        host, {"span_x_mm": [-1, 1], "axis_yz_mm": [0, 0], "radius_mm": 1}
    )
    assert all(r["clear"] for r in result["all_boundary_faces"])
    assert not result["core_anchor_outside"]
    assert result["status"] == "UNPROVEN"
