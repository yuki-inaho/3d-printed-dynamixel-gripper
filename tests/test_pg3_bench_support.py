import cadquery as cq
import pytest

from gripper_design.pg3_bench_support import build_support, to_print, to_world
from scripts.assembly_io import bounds
from scripts.step_cache import read_rows


@pytest.fixture(scope="module")
def shapes():
    return {
        r.name: r.world
        for r in read_rows("outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step")
    }


def test_single_printable_support_with_four_source_derived_seats(shapes):
    result = build_support(shapes)
    assert "print_shape" in result and "world_shape" in result
    local = result["print_shape"]
    assert local.isValid() and len(local.Solids()) == 1 and local.Volume() > 0
    assert bounds(local) == pytest.approx([-24, -30, 0, 24, 30, 6.55], abs=1e-6)
    assert len(result["seats"]) == 4
    for kind in ("drive", "carriage"):
        for side in ("R", "L"):
            row = result["seats"][f"PG3_pivot_{kind}_{side}_nut"]
            assert row["post_height_mm"] == pytest.approx(1.2 if kind == "drive" else 3.55)
            assert row["nut_back_x_mm"] == pytest.approx(20.5 if kind == "drive" else 22.85)


def test_exported_support_contacts_and_tip_clearance(shapes, tmp_path):
    from scripts.review_pg3_bench_support import inspect_support

    design = build_support(shapes)
    path = tmp_path / "support.step"
    cq.exporters.export(design["print_shape"], str(path))
    loaded = cq.importers.importStep(str(path)).val()
    result = inspect_support(to_world(loaded, design["frame"]), design, shapes)
    assert result["nominal_static_pass"]
    assert result["body_pairs"]["counts"] == {"PASS": 17}
    assert result["tool_pairs"]["counts"] == {"PASS": 144}
    assert all(v["pass_contact"] for v in result["nut_seats"].values())


def test_high_support_and_plugged_tip_are_real_collisions(shapes):
    from scripts.review_pg3 import inspect_pairs
    from scripts.review_pg3_bench_support import inspect_support

    design = build_support(shapes)
    nut = "PG3_pivot_drive_R_nut"
    high = design["world_shape"].translate((0.2, 0, 0))
    result = inspect_pairs({"jig": high, nut: shapes[nut]}, [("jig", nut)])
    assert result["counts"] == {"FAIL": 1}
    assert not inspect_support(high, design, shapes)["nominal_static_pass"]
    row = design["seats"][nut]
    x, y = row["print_xy_mm"]
    plug = cq.Solid.makeCylinder(1.3, row["post_top_print_z_mm"], (x, y, 0))
    bad = to_world(design["print_shape"].fuse(plug), design["frame"])
    bolt = row["bolt_name"]
    result = inspect_pairs({"jig": bad, bolt: shapes[bolt]}, [("jig", bolt)])
    assert result["counts"] == {"FAIL": 1}
    assert not inspect_support(bad, design, shapes)["nominal_static_pass"]


def test_frame_is_rigid_and_right_handed(shapes):
    from scripts.review_pg3_washer_contacts import controlled_containment

    design = build_support(shapes)
    original = design["print_shape"]
    returned = to_print(to_world(original, design["frame"]), design["frame"])
    assert controlled_containment(original, returned, equal=True)["pass"]
    origin = cq.Vertex.makeVertex(0, 0, 0)
    axes = [cq.Vertex.makeVertex(*a) for a in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    centre = to_world(origin, design["frame"]).Center()
    actual = [(to_world(a, design["frame"]).Center() - centre) for a in axes]
    assert actual[0].cross(actual[1]).dot(actual[2]) == pytest.approx(1)
    assert actual[2].toTuple() == pytest.approx((1, 0, 0), abs=1e-12)


@pytest.mark.parametrize("post,tip", [(1.9, 1), (1.9, 1.9), (-1, 1.2), (float("nan"), 1.2)])
def test_invalid_post_dimensions_rejected(shapes, post, tip):
    with pytest.raises(ValueError):
        build_support(shapes, post_radius_mm=post, tip_radius_mm=tip)
