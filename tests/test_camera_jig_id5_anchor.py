"""CAD-only anchor checks for the proposed ID5 motor-top camera support."""

from pathlib import Path

import pytest

from camera_jig.id5_corner_anchor import validate_id5_case_anchor
from gripper_design.build import _source_rows
from scripts.step_cache import read_rows

ROOT = Path(__file__).resolve().parents[1]
MID_STEP = ROOT / "outputs/pg3-id5-p05-windows-r2/ID5_mid_P05_windows_CANDIDATE.step"


@pytest.fixture(scope="module")
def motor_shapes():
    source = next(row.world for row in _source_rows() if row.name == "M05_ref00")
    rows = read_rows(MID_STEP)
    fixed = next(row.world for row in rows if row.name == "PG3_XL430_fixed")
    horn = next(row.world for row in rows if row.name == "PG3_XL430_horn")
    return source, fixed, horn


def test_source_and_saved_candidate_have_same_case_top_mounting_pattern(motor_shapes):
    source, fixed, _ = motor_shapes

    source_report = validate_id5_case_anchor(source)
    candidate_report = validate_id5_case_anchor(fixed)

    assert source_report == candidate_report
    assert source_report["centers_xy_mm"] == [
        (-8.2, 158.9),
        (-8.2, 170.9),
        (7.8, 158.9),
        (7.8, 170.9),
    ]
    assert source_report["trimmed_depths_mm"] == [4.0] * 4


def test_report_ignores_mesh_left_by_earlier_rendering(motor_shapes):
    """A cached shape tessellated by another test must measure the same."""
    source, _, _ = motor_shapes
    clean = validate_id5_case_anchor(source.copy())
    meshed = source.copy()
    meshed.tessellate(0.5, 0.5)
    assert validate_id5_case_anchor(meshed) == clean


def test_shifted_case_is_rejected(motor_shapes):
    _, fixed, _ = motor_shapes

    with pytest.raises(ValueError, match="hole centers"):
        validate_id5_case_anchor(fixed.translate((0.5, 0, 0)))


def test_horn_cannot_be_used_as_case_anchor(motor_shapes):
    _, _, horn = motor_shapes

    with pytest.raises(ValueError, match="Expected four"):
        validate_id5_case_anchor(horn)
