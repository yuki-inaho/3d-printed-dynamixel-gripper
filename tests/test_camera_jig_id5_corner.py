"""Contract tests for a case-fixed, tool-accessible ID5 camera mount candidate."""

import math
from itertools import product

import cadquery as cq
import pytest
from cadre.probes import cylinder_surface_sense
from OCP.BRepAdaptor import BRepAdaptor_Surface

from camera_jig.build import common_volume, donor_parts
from camera_jig.id5_corner import build_candidate, validate_candidate
from camera_jig.id5_corner_anchor import EXPECTED_CENTERS_XY_MM, EXPECTED_TOP_Z_MM


def hole_centers(shape, diameter_mm, axis_index):
    centers = set()
    for face in shape.Faces():
        if face.geomType() != "CYLINDER" or cylinder_surface_sense(face) != "concave":
            continue
        cylinder = BRepAdaptor_Surface(face.wrapped).Cylinder()
        if abs(2 * cylinder.Radius() - diameter_mm) > 0.01:
            continue
        direction = cylinder.Axis().Direction()
        if abs((direction.X(), direction.Y(), direction.Z())[axis_index]) < 0.999:
            continue
        point = cylinder.Location()
        coordinates = (point.X(), point.Y(), point.Z())
        centers.add(
            tuple(round(coordinates[index], 3) for index in range(3) if index != axis_index)
        )
    return centers


def test_case_base_has_four_holes_at_actual_motor_top_centers():
    candidate = build_candidate()

    assert hole_centers(candidate["base"], 2.8, 2) == set(product((-8.2, 7.8), (158.9, 170.9)))


def test_camera_carrier_keeps_28_mm_square_pattern_and_downward_axis():
    candidate = build_candidate()
    local_carrier = candidate["camera_carrier"].moved(candidate["carrier_location"].inverse)

    assert hole_centers(local_carrier, 2.4, 2) == set(product((-14.0, 14.0), repeat=2))
    assert candidate["optical_axis"][1] > 0
    assert candidate["optical_axis"][2] < 0


def test_misplaced_or_wrong_pitch_candidate_is_rejected():
    with pytest.raises(ValueError, match="case anchor"):
        validate_candidate(build_candidate(anchor_shift_x_mm=0.5))
    with pytest.raises(ValueError, match="camera pattern"):
        validate_candidate(build_candidate(camera_pitch_mm=26.0))


def test_base_does_not_overlap_separate_carrier():
    candidate = build_candidate()

    assert common_volume(candidate["base"], candidate["camera_carrier"]) < 1e-4


def test_nominal_5_mm_driver_can_reach_case_holes_before_carrier_is_installed():
    base = build_candidate()["base"]
    for x, y in EXPECTED_CENTERS_XY_MM:
        driver = cq.Solid.makeCylinder(
            2.5, 40, cq.Vector(x, y, EXPECTED_TOP_Z_MM + 3.01), cq.Vector(0, 0, 1)
        )
        assert common_volume(base, driver) < 1e-4


def test_two_carrier_attachment_holes_are_coaxial_in_both_parts():
    candidate = build_candidate()
    local_base = candidate["base"].moved(candidate["carrier_location"].inverse)
    local_carrier = candidate["camera_carrier"].moved(
        candidate["carrier_location"].inverse
    )
    centers = {(-6.0, -25.5), (6.0, -25.5)}

    assert hole_centers(local_base, 3.4, 2) == centers
    assert hole_centers(local_carrier, 3.4, 2) == centers


def test_reference_camera_back_envelope_clears_support():
    candidate = build_candidate()
    proxy_local = cq.Solid.makeBox(38, 38, 25, cq.Vector(-19, -19, -25))
    proxy_world = proxy_local.moved(candidate["carrier_location"])

    assert common_volume(candidate["base"], proxy_world) < 1e-4


def test_unconfirmed_reference_camera_does_not_penetrate_mount():
    candidate = build_candidate()
    _, raw_reference_camera = donor_parts()
    reference = raw_reference_camera.rotate((0, 0, 0), (1, 0, 0), 90).moved(
        candidate["carrier_location"]
    )

    assert common_volume(candidate["base"], reference) < 1e-4
    assert common_volume(candidate["camera_carrier"], reference) < 1e-4


def test_each_mount_hole_has_2_5_mm_radial_material_at_72_angles():
    candidate = build_candidate()
    local_base = candidate["base"].moved(candidate["carrier_location"].inverse)
    local_carrier = candidate["camera_carrier"].moved(
        candidate["carrier_location"].inverse
    )
    groups = (
        (candidate["base"], EXPECTED_CENTERS_XY_MM, 1.4, EXPECTED_TOP_Z_MM + 1.5),
        (local_base, ((-6.0, -25.5), (6.0, -25.5)), 1.7, -2.0),
        (local_carrier, set(product((-14.0, 14.0), repeat=2)), 1.2, 1.5),
        (local_carrier, ((-6.0, -25.5), (6.0, -25.5)), 1.7, 1.5),
    )
    for shape, centers, hole_radius, height in groups:
        for x, y in centers:
            for index in range(72):
                angle = 2 * math.pi * index / 72
                ring = cq.Vector(
                    x + (hole_radius + 2.49) * math.cos(angle),
                    y + (hole_radius + 2.49) * math.sin(angle),
                    height,
                )
                assert shape.isInside(ring, 1e-6), (x, y, index)
