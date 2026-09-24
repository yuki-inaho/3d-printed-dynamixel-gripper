import cadquery as cq
import pytest

from gripper_design.pg3 import PG3Model, to_arm
from scripts.review_pg3_drive_fasteners import countersink_contact, inspect_receivers


@pytest.fixture(scope="module")
def shapes():
    return {f"PG3_{n}": to_arm(s) for n, s in PG3Model().at(90).items()}


def test_six_nominal_receivers_have_axis_and_depth_evidence(shapes):
    report = inspect_receivers(shapes)
    assert len(report["fasteners"]) == 6
    for name, row in report["fasteners"].items():
        assert row["nominal_receiver_geometry_pass"]
        assert row["outside_allowed_region_clear"]
        horn = "horn_bolt" in name
        assert row["insertion_from_seat_mm"] == pytest.approx(2.5 if horn else 2.65)
        assert row["tip_to_depth_limit_mm"] == pytest.approx(1 if horn else 1.35)
        if not horn:
            assert row["countersink"]["nominal_seating_pass"]
            assert row["countersink"]["contact_area_mm2"] > 20


@pytest.mark.parametrize(
    "name,shift",
    [
        ("PG3_horn_bolt_0", (0, 0.4, 0)),
        ("PG3_horn_bolt_0", (-1.2, 0, 0)),
        ("PG3_case_tapper_11", (0, 0.5, 0)),
        ("PG3_case_tapper_11", (-1.6, 0, 0)),
        ("PG3_case_tapper_11", (0.2, 0, 0)),
    ],
)
def test_displaced_or_bottoming_fastener_is_not_an_allowed_thread_contact(shapes, name, shift):
    moved = shapes | {name: shapes[name].translate(shift)}
    report = inspect_receivers(moved)
    assert not report["fasteners"][name]["nominal_receiver_geometry_pass"]


def test_two_overlapping_male_cones_are_not_a_countersink_seat():
    first = cq.Solid.makeCone(1.45, 2.75, 1.3, (18, 0, 0), (1, 0, 0))
    second = cq.Solid.makeCone(1.3, 2.6, 1.3, (17.85, 0, 0), (1, 0, 0))
    assert not countersink_contact(first, second, (0, 0))["nominal_seating_pass"]
