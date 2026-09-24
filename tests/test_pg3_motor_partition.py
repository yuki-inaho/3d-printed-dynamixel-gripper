import math

import cadquery as cq
import pytest

import scripts.review_pg3_motor_partition as checker
from gripper_design.pg3 import PG3Model, to_arm
from scripts.review_pg3_motor_partition import inspect_partition, partition_face


def test_horn_pushed_into_fixed_body_is_not_accepted():
    fixed = cq.Solid.makeCylinder(5, 3, (-3, 0, 0), (1, 0, 0))
    horn = cq.Solid.makeCylinder(2, 2, (-0.2, 0, 0), (1, 0, 0))
    assert fixed.intersect(horn).Volume() > 2
    result = inspect_partition(fixed, horn, (0, 0), 2.1)
    assert not result["nominal_partition_pass"]
    assert result["status"] == "UNPROVEN", result


@pytest.fixture(scope="module")
def actual():
    shapes = PG3Model().neutral
    return to_arm(shapes["XL430_fixed"]), to_arm(shapes["XL430_horn"])


def test_actual_all_boundaries_have_evidence_and_padding_is_counted(actual):
    fixed, horn = actual
    result = inspect_partition(fixed, horn)
    assert result["status"] == "BOUNDED_PARTITION_CONTACT", result
    assert [r["face"] for r in result["all_boundary_faces"]] == list(range(len(fixed.Faces())))
    assert 0 < result["contact_volume_upper_bound_mm3"] < 1e-4
    assert result["possible_contact_slab_thickness_mm"] == pytest.approx(2e-7, abs=1e-10)
    assert not result["positive_clearance_proven"]
    assert not result["physical_motor_interface_approved"]
    assert not result["installation_approved"]


def test_problem_face_is_partitioned_without_losing_boundary(actual):
    face = actual[0].Faces()[96]
    axis = cq.Edge.makeLine((-20, 234.9, 164.6), (22, 234.9, 164.6))
    front, evidence = partition_face(face, 15.3)
    assert face.distance(axis) == pytest.approx(10)
    assert front.distance(axis) > 11
    assert evidence["residual_areas_mm2"] == [0, 0, 0]
    assert evidence["conservation_error_mm2"] < 1e-10


def test_missing_piece_in_partition_union_is_rejected(actual, monkeypatch):
    monkeypatch.setattr(cq.Compound, "fuse", lambda self, *args, **kwargs: self)
    with pytest.raises(ValueError, match="loses"):
        partition_face(actual[0].Faces()[96], 15.3)


def test_added_solid_inside_sweep_is_not_dropped():
    fixed = cq.Solid.makeCylinder(5, 3, (-3, 0, 0), (1, 0, 0))
    horn = cq.Solid.makeCylinder(2, 2, (0, 0, 0), (1, 0, 0))
    intrusion = cq.Solid.makeBox(1, 1, 1, (0.5, -0.5, -0.5))
    assert intrusion.intersect(horn).Volume() == pytest.approx(1)
    result = inspect_partition(cq.Compound.makeCompound([fixed, intrusion]), horn, (0, 0), 2.1)
    assert result["status"] == "UNPROVEN", result
    assert len(result["all_boundary_faces"]) == len(fixed.Faces()) + len(intrusion.Faces())


def test_contact_slab_exceeding_volume_budget_is_not_discarded():
    fixed = cq.Solid.makeCylinder(5, 3, (-3, 0, 0), (1, 0, 0))
    horn = cq.Solid.makeCylinder(2, 2, (0, 0, 0), (1, 0, 0))
    result = inspect_partition(fixed, horn, (0, 0), 100)
    assert result["forward_region_proven_empty"]
    assert result["contact_volume_upper_bound_mm3"] > 1e-4
    assert result["status"] == "UNPROVEN"


def test_face_evaluation_error_is_not_successful_negative(actual, monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("face self-control failed")

    monkeypatch.setattr(checker, "face_control", broken)
    result = inspect_partition(*actual)
    assert result["status"] == "ERROR"
    assert not result["nominal_partition_pass"]


def test_nonfinite_area_is_rejected():
    class Broken:
        def Area(self):
            return math.nan

        def isValid(self):
            return True

    with pytest.raises(ValueError, match="nonfinite"):
        checker.area(Broken())


def test_inverted_material_is_not_a_valid_source(actual):
    fixed, horn = actual
    inverted = fixed.Solids()[0].copy()
    inverted.wrapped.Reverse()
    result = inspect_partition(inverted, horn)
    assert result["status"] == "ERROR"
