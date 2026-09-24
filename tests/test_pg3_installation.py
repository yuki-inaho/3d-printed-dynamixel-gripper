import cadquery as cq
import pytest

from gripper_design.pg3 import PG3Model, to_arm
from gripper_design.pg3_installation import original_support, support_candidate, support_change_mask


def test_support_preserves_outside_mask_and_load_path():
    original = original_support()
    updated = support_candidate()
    mask = support_change_mask()
    assert updated.isValid() and len(updated.Solids()) == 1
    assert 9000 < updated.Volume() < original.Volume()
    assert updated.cut(original).Volume() < 1e-4
    assert original.cut(updated).cut(mask).Volume() < 1e-4
    # Protected loaded regions: all bolt shanks plus 4 mm radial material.
    for x in (-6.2, 5.8):
        for y in (206.9, 230.9):
            region = cq.Solid.makeCylinder(5.2, 4, (x, y, 146.35))
            # The user-authorized bore change is local to diameter 2.8 mm.
            region = region.cut(cq.Solid.makeCylinder(1.4, 4, (x, y, 146.35)))
            assert original.intersect(region).cut(updated).Volume() < 1e-4
    upstream = cq.Solid.makeBox(40, 10, 40, (-20, 183, 144))
    assert original.intersect(upstream).cut(updated).cut(mask).Volume() < 1e-4


def test_original_interference_is_removed_without_touching_frame():
    model = PG3Model()
    frame = to_arm(model.neutral["frame"])
    old = original_support()
    new = support_candidate()
    assert old.intersect(frame).Volume() == pytest.approx(240.5625, abs=1e-5)
    assert new.intersect(frame).Volume() < 1e-4
    assert new.distance(frame) == pytest.approx(0.5)
    for angle in range(25, 136, 5):
        for name, shape in model.at(angle).items():
            if name.startswith(("carriage", "finger", "pivot_")):
                assert new.intersect(to_arm(shape)).Volume() < 1e-4, (angle, name)


def test_case_mount_passes_tapper_and_rejects_original_small_holes():
    old, new = original_support(), support_candidate()
    for x in (-6.2, 5.8):
        for y in (206.9, 230.9):
            shank = cq.Solid.makeCylinder(1.3, 4, (x, y, 146.35))
            assert old.intersect(shank).Volume() > 3
            assert new.intersect(shank).Volume() < 1e-5
            assert new.distance(shank) == pytest.approx(0.1, abs=1e-6)


def test_side_camera_keeps_reference_pattern_and_contact():
    from camera_jig.build import CAMERA_LOC, LINK, camera_bores, common_volume
    from gripper_design.pg3_installation import SIDE_CAMERA_LOC, side_camera_parts

    parts = side_camera_parts()
    carrier = parts["camera_carrier"].moved(SIDE_CAMERA_LOC.inverse)
    unrotated = carrier.rotate((0, 0, 0), (0, 0, 1), 180).moved(CAMERA_LOC)
    holes = camera_bores(unrotated)
    assert len(holes) == 4
    assert sorted(tuple(round(v, 6) for v in h["xy_mm"]) for h in holes) == [
        (-14, -14),
        (-14, 14),
        (14, -14),
        (14, 14),
    ]
    assert all(h["diameter_mm"] == pytest.approx(2.4) for h in holes)
    link = cq.importers.importStep(str(LINK)).val()
    for shape in parts.values():
        assert shape.isValid() and len(shape.Solids()) == 1
        assert common_volume(shape, link) < 1e-5
    assert common_volume(parts["saddle"].translate((0, 0.01, 0)), link) / 0.01 > 500
    assert common_volume(parts["front_jaw"].translate((0, -0.01, 0)), link) / 0.01 > 500
    assert (
        common_volume(parts["camera_carrier"].translate((0, -0.01, 0)), parts["saddle"]) / 0.01
        > 100
    )


def test_case_axes_and_depth_against_actual_mating_cad():
    from gripper_design.build import _source_rows
    from gripper_design.pg3_installation import case_attachment_report

    motor = next(r.world for r in _source_rows() if r.name == "M06_ref00")
    report = case_attachment_report(motor)
    assert report["nominal_geometry_pass"]
    assert report["max_axis_error_mm"] < 1e-6
    assert report["minimum_tip_to_bottom_mm"] == pytest.approx(0.5)
    assert not case_attachment_report(motor.translate((1, 0, 0)))["nominal_geometry_pass"]
    assert not case_attachment_report(motor.translate((0, 0, 1)))["nominal_geometry_pass"]
    assert not case_attachment_report(motor, screw_length=10)["nominal_geometry_pass"]
    assert not case_attachment_report(motor, screw_length=5)["nominal_geometry_pass"]


def test_upstream_horn_stack_and_wrong_length_controls():
    from gripper_design.build import _source_rows
    from gripper_design.pg3_installation import horn_attachment_report

    motor = next(r.world for r in _source_rows() if r.name == "M05_ref00")
    report = horn_attachment_report(motor, support_candidate())
    assert report["nominal_geometry_pass"]
    assert sorted(r["support_thickness_mm"] for r in report["bores"]) == pytest.approx([4, 4, 4, 4])
    assert sorted(r["screw_length_mm"] for r in report["bores"]) == [8, 8, 8, 8]
    assert all(r["nominal_engagement_mm"] == pytest.approx(3) for r in report["bores"])
    assert all(r["tip_to_bottom_mm"] == pytest.approx(0.5) for r in report["bores"])
    assert not horn_attachment_report(motor.translate((1, 0, 0)), support_candidate())[
        "nominal_geometry_pass"
    ]
    assert not horn_attachment_report(motor.translate((0, -1, 0)), support_candidate())[
        "nominal_geometry_pass"
    ]
    assert not horn_attachment_report(motor, support_candidate(), length_adjustment=2)[
        "nominal_geometry_pass"
    ]
    assert not horn_attachment_report(motor, support_candidate(), length_adjustment=-2)[
        "nominal_geometry_pass"
    ]


def test_horn_fasteners_fit_and_lower_spacer_has_a_full_seat():
    import math

    from gripper_design.pg3_installation import horn_hardware

    hardware = horn_hardware()
    new = support_candidate()
    for shape in hardware.values():
        assert new.intersect(shape).Volume() < 1e-5
    spacer = hardware["ARM_P06_horn_spacer_1_ENVELOPE"]
    contact = new.intersect(spacer.translate((0, -0.01, 0))).Volume() / 0.01
    # Bearing footprint excludes the larger support bore (R1.2), not just the
    # spacer's smaller centre opening (R1.1).
    assert contact == pytest.approx(math.pi * (2.15**2 - 1.2**2), abs=1e-5)
    assert original_support().intersect(spacer).Volume() > 1


def test_camera_bridge_has_broad_top_root_load_path():
    from gripper_design.pg3_installation import side_camera_parts

    saddle = side_camera_parts()["saddle"]
    root = cq.Solid.makeBox(12, 10, 6, (20, 130.4, 196.6))
    assert root.cut(saddle).Volume() < 1e-5
