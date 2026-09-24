import pytest

from gripper_design.build import build_terminal_pose, terminal_pose_set


def test_terminal_pose_set_keeps_all_xl430_interface_and_release_closed():
    poses = terminal_pose_set()
    assert set(poses) == {"minimum", "center", "maximum"}
    assert [poses[name].opening_mm for name in ("minimum", "center", "maximum")] == pytest.approx(
        [32.0, 40.0, 48.0]
    )
    for pose in poses.values():
        assert pose.interface_pitch_circle_diameter_mm == pytest.approx(16.0)
        assert pose.fabrication_approved is False


def test_terminal_replaces_old_r3_gripper_but_keeps_motor_and_p05():
    result = build_terminal_pose(theta_rad=0.0)
    assert {"P06_fixed_gripper_XL430", "P07_moving_gripper_XL430"} == set(
        result.replaced_source_units
    )
    assert "P05_wrist_XL430" in result.retained_source_units
    assert "M06" in result.retained_source_units
    assert "P06_fixed_gripper_XL430" not in result.retained_source_units
    assert "P07_moving_gripper_XL430" not in result.retained_source_units


def test_terminal_reports_full_occurrence_coverage_and_unknown_physics():
    result = build_terminal_pose(theta_rad=0.0)
    counts = result.occurrence_coverage
    assert sum(counts.values()) == result.source_occurrence_count
    assert set(counts) == {"solid", "shell", "wire", "empty"}
    assert result.mass_kg is None
    assert result.center_of_mass_status == "volume_centroid_only_density_unknown"
    assert result.fastener_status == "candidate_unpurchased"
    assert result.tool_status == "nominal_envelope_only"
    assert result.output_contact_distance_mm == pytest.approx(0.0)
    assert result.output_contact_area_probe_mm2 > 200.0
