import json

import numpy as np
import pytest

from simulation.calibrate import (
    CalibrationDatasetError,
    calibrate_run,
    reprojection_rms_px,
    validate_pose_diversity,
)


def test_synthetic_calibration_meets_fixed_truth_gates(tmp_path, calibration_inputs):
    detections, truth = calibration_inputs
    result = calibrate_run(detections, truth, tmp_path / "calibration")
    report = json.loads(result.json_path.read_text())

    assert report["synthetic_validation_passed"] is True
    assert report["accepted_frame_count"] >= 12
    assert report["metrics"]["reprojection_rms_px"] <= 0.5
    assert report["metrics"]["fx_relative_error"] <= 0.01
    assert report["metrics"]["fy_relative_error"] <= 0.01
    assert report["metrics"]["cx_absolute_error_px"] <= 2.0
    assert report["metrics"]["cy_absolute_error_px"] <= 2.0
    assert max(frame["rotation_error_deg"] for frame in report["frames"]) <= 0.5
    assert max(frame["translation_error_mm"] for frame in report["frames"]) <= 2.0
    assert report["real_camera_calibration_approved"] is False


def test_wrong_tag_scale_is_rejected_by_translation_truth_gate(tmp_path, calibration_inputs):
    detections, truth = calibration_inputs
    result = calibrate_run(
        detections,
        truth,
        tmp_path / "wrong-scale",
        object_scale=1.25,
    )
    report = json.loads(result.json_path.read_text())

    assert report["synthetic_validation_passed"] is False
    assert "translation_error" in report["failed_gates"]
    assert max(frame["translation_error_mm"] for frame in report["frames"]) > 50.0


def test_single_pose_dataset_is_rejected_before_calibration(tmp_path, calibration_inputs):
    detections_path, truth = calibration_inputs
    detections = json.loads(detections_path.read_text())
    detections["frames"] = detections["frames"][:1]
    path = tmp_path / "single-pose.json"
    path.write_text(json.dumps(detections))

    with pytest.raises(CalibrationDatasetError, match="at least 12"):
        calibrate_run(path, truth, tmp_path / "single-result")


def test_pose_diversity_rejects_repeated_planar_view():
    rvecs = [np.zeros((3, 1), dtype=float) for _ in range(12)]
    tvecs = [np.array([[0.0], [0.0], [0.4]]) for _ in range(12)]

    with pytest.raises(CalibrationDatasetError, match="pose diversity"):
        validate_pose_diversity(rvecs, tvecs)


def test_reprojection_rms_is_distance_per_corner_not_coordinate_component():
    assert reprojection_rms_px(np.array([[3, 4], [3, 4]])) == pytest.approx(5)
    with pytest.raises(CalibrationDatasetError):
        reprojection_rms_px(np.array([[float("nan"), 0]]))
