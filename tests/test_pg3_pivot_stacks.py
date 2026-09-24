import pytest

from gripper_design.pg3 import PG3Model, to_arm
from scripts.review_pg3_pivot_stacks import inspect_pivots


@pytest.fixture
def assembly():
    return {f"PG3_{n}": to_arm(s) for n, s in PG3Model().at(90).items()}


def test_nominal_four_pivots_keep_links_unclamped(assembly):
    report = inspect_pivots(assembly)
    assert report["nominal_pivot_geometry_pass"]
    assert len(report["pivots"]) == 4
    for row in report["pivots"].values():
        assert row["rear_axial_gap_mm"] == pytest.approx(0.3)
        assert row["front_axial_gap_mm"] == pytest.approx(0.3)
        assert row["radial_gap_mm"] == pytest.approx(0.2)
        assert row["retaining_overlap_mm"] == pytest.approx(0.8)


@pytest.mark.parametrize(
    "name,offset",
    [
        ("PG3_pivot_drive_R_washer", (-0.31, 0, 0)),
        ("PG3_link_R", (0.31, 0, 0)),
        ("PG3_link_R", (0, 0.25, 0)),
        ("PG3_pivot_carriage_L_bolt", (3, 0, 0)),
    ],
)
def test_shifted_parts_do_not_pass_clamp_stack(assembly, name, offset):
    assembly[name] = assembly[name].translate(offset)
    assert not inspect_pivots(assembly)["nominal_pivot_geometry_pass"]


def test_nut_cannot_penetrate_its_printed_seat(assembly):
    name = "PG3_pivot_drive_R_nut"
    assembly[name] = assembly[name].translate((0.2, 0, 0))
    assert not inspect_pivots(assembly)["nominal_pivot_geometry_pass"]


def test_headless_pin_is_not_a_clamping_bolt(assembly):
    import cadquery as cq

    row = inspect_pivots(assembly)["pivots"]["PG3_pivot_drive_R"]["interfaces"]["shank"]
    lo, hi = row["span_x_mm"]
    y, z = row["axis_yz_mm"]
    assembly["PG3_pivot_drive_R_bolt"] = cq.Solid.makeCylinder(1, hi - lo, (lo, y, z), (1, 0, 0))
    with pytest.raises(ValueError, match="missing convex cylindrical interface R1.9"):
        inspect_pivots(assembly)
