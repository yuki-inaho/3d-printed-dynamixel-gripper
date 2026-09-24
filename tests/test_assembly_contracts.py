import cadquery as cq
import pytest

from gripper_design.assembly_contracts import (
    AssemblyOccurrence,
    HoleAxis,
    PlanarSeat,
    check_hole_correspondence,
    check_occurrence_coverage,
    check_planar_mate,
)


def _seat(z: float, normal: tuple[float, float, float]) -> PlanarSeat:
    face = cq.Workplane("XY", origin=(0, 0, z)).rect(20, 20).val()
    return PlanarSeat(face=face, origin=(0, 0, z), normal=normal)


def test_coaxial_parts_with_two_mm_seat_gap_fail():
    upstream = _seat(0.0, (0, 0, 1))
    downstream = _seat(2.0, (0, 0, -1))

    result = check_planar_mate(upstream, downstream)

    assert result.status == "FAIL"
    assert result.reason_id == "seat_gap"
    assert result.metrics["gap_mm"] == pytest.approx(2.0)


def test_same_direction_seat_normals_fail():
    upstream = _seat(0.0, (0, 0, 1))
    downstream = _seat(0.0, (0, 0, 1))

    result = check_planar_mate(upstream, downstream)

    assert result.status == "FAIL"
    assert result.reason_id == "seat_normals_not_opposed"


def test_overlapping_shell_is_not_silently_dropped():
    candidate = cq.Workplane("XY").box(10, 10, 10).val()
    obstacle_shell = cq.Workplane("YZ", origin=(0, 0, 0)).rect(20, 20).val()
    occurrences = [
        AssemblyOccurrence("candidate", "solid", candidate),
        AssemblyOccurrence("barrier", "shell", obstacle_shell),
    ]

    result = check_occurrence_coverage(occurrences, candidate_name="candidate")

    assert result.status == "UNKNOWN"
    assert result.reason_id == "non_solid_overlap_requires_resolution"
    assert result.metrics["shell_count"] == 1


def test_missing_occurrence_is_error_not_zero_collision():
    occurrences = [AssemblyOccurrence("candidate", "solid", None)]

    result = check_occurrence_coverage(occurrences, candidate_name="candidate")

    assert result.status == "ERROR"
    assert result.reason_id == "missing_geometry"


def test_geometry_kernel_error_is_not_reported_as_clearance_pass():
    class BrokenGeometry:
        def BoundingBox(self):
            raise RuntimeError("synthetic kernel failure")

    occurrences = [
        AssemblyOccurrence("candidate", "solid", cq.Workplane("XY").box(1, 1, 1).val()),
        AssemblyOccurrence("broken", "shell", BrokenGeometry()),
    ]

    result = check_occurrence_coverage(occurrences, candidate_name="candidate")

    assert result.status == "ERROR"
    assert result.reason_id == "geometry_query_failed"
    assert "synthetic kernel failure" in result.detail


def test_known_good_seats_and_four_holes_pass():
    first_seat = _seat(0.0, (0, 0, 1))
    second_seat = _seat(0.0, (0, 0, -1))
    first_holes = [
        HoleAxis((x, y, 0), (0, 0, 1), 2.0) for x, y in ((8, 0), (0, 8), (-8, 0), (0, -8))
    ]
    second_holes = list(reversed(first_holes))

    seat_result = check_planar_mate(first_seat, second_seat)
    hole_result = check_hole_correspondence(first_holes, second_holes)

    assert seat_result.status == "PASS"
    assert seat_result.metrics["trimmed_contact_area_mm2"] == pytest.approx(400.0)
    assert hole_result.status == "PASS"
    assert len(hole_result.metrics["matches"]) == 4


def test_ring_and_disk_with_overlapping_bounding_boxes_do_not_mate():
    ring = cq.Workplane("XY").circle(10).circle(6).extrude(1).faces(">Z").val()
    disk = cq.Face.makeFromWires(cq.Wire.makeCircle(5, cq.Vector(0, 0, 1), cq.Vector(0, 0, 1)))
    result = check_planar_mate(
        PlanarSeat(ring, (0, 0, 1), (0, 0, 1)),
        PlanarSeat(disk, (0, 0, 1), (0, 0, -1)),
    )
    assert result.status == "FAIL"
    assert result.metrics["trimmed_contact_area_mm2"] == pytest.approx(0)


def test_inclined_seat_uses_actual_area_not_projected_bounding_box():
    face = cq.Face.makeFromWires(cq.Workplane("XY").rect(20, 20).val())
    face = face.rotate((0, 0, 0), (1, 0, 0), 45)
    normal = (0, -(0.5**0.5), 0.5**0.5)
    result = check_planar_mate(
        PlanarSeat(face, (0, 0, 0), normal),
        PlanarSeat(face, (0, 0, 0), tuple(-v for v in normal)),
    )
    assert result.status == "PASS"
    assert result.metrics["trimmed_contact_area_mm2"] == pytest.approx(400)


def test_coverage_records_all_partners_after_unknown_fail_and_missing_geometry():
    box = cq.Workplane("XY").box(10, 10, 10).val()
    occurrences = [
        AssemblyOccurrence("candidate", "solid", box),
        AssemblyOccurrence("shell", "shell", box.Shells()[0]),
        AssemblyOccurrence("collision", "solid", box),
        AssemblyOccurrence("missing", "solid", None),
        AssemblyOccurrence("clear", "solid", box.translate((30, 0, 0))),
    ]
    result = check_occurrence_coverage(occurrences, candidate_name="candidate")
    assert result.status == "ERROR"
    assert len(result.metrics["occurrence_inventory"]) == 5
    assert result.metrics["solid_count"] == 4
    assert {row["resolution"] for row in result.metrics["occurrence_inventory"]} >= {
        "unresolved_overlap",
        "interference",
        "missing_geometry",
        "bounding_box_clear",
    }
