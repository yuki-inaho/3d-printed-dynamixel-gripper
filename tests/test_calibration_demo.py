import pytest

from scripts.run_calibration_demo import verify_run


def test_headless_e2e_manifest_and_artifacts_verify(synthetic_run):
    summary = verify_run(synthetic_run)
    assert summary["artifact_count"] >= 40
    assert summary["rendered_frame_count"] == 12
    assert summary["accepted_detection_frame_count"] == 12
    assert summary["cad_view_count"] == 4
    assert summary["synthetic_validation_passed"] is True


def test_missing_manifest_is_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        verify_run(tmp_path)


def test_empty_evidence_cannot_pass_with_success_flags(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "inputs": [],
                "artifacts": [],
                "rejected_frames": [],
                "synthetic_validation_passed": True,
                "rendered_frame_count": 12,
                "accepted_detection_frame_count": 12,
                "cad_views": [],
            }
        )
    )
    with pytest.raises(ValueError):
        verify_run(tmp_path)


import json
