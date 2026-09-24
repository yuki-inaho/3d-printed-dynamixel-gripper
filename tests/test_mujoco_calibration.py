import json

import numpy as np
import pytest

from simulation.mujoco_scene import (
    CameraView,
    assess_frame,
    default_camera_views,
    render_calibration_run,
)


def test_default_views_are_distinct_and_cover_three_distances():
    views = default_camera_views()
    positions = {tuple(view.position_world_m) for view in views}
    distances = {round(float(np.linalg.norm(view.position_world_m)), 2) for view in views}

    assert len(views) >= 12
    assert len(positions) == len(views)
    assert len(distances) >= 3


def test_frame_assessment_rejects_black_duplicate_backside_and_outside():
    image = np.full((480, 640, 3), 127, dtype=np.uint8)
    image[120:360, 160:480] = 255
    inside = np.array([[100, 100], [540, 100], [540, 380], [100, 380]], dtype=float)
    accepted = assess_frame(image, inside, board_front_facing=True, prior_hashes=set())
    assert accepted.accepted is True

    assert assess_frame(np.zeros_like(image), inside, True, set()).reason == "black_image"
    assert assess_frame(image, inside, True, {accepted.sha256}).reason == "duplicate_frame"
    assert assess_frame(image, inside, False, set()).reason == "board_backside"
    outside = inside + np.array([1000.0, 0.0])
    assert assess_frame(image, outside, True, set()).reason == "board_outside_image"


def test_camera_view_rejects_eye_at_target():
    with pytest.raises(ValueError, match="eye and target"):
        CameraView("bad", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))


def test_renderer_requires_explicit_backend(monkeypatch, tmp_path):
    monkeypatch.delenv("MUJOCO_GL", raising=False)
    with pytest.raises(RuntimeError, match="explicitly set"):
        render_calibration_run(
            board_directory=tmp_path / "not-required-before-backend-check",
            output_directory=tmp_path / "render-run",
        )


def test_headless_render_writes_nonidentical_images_and_truth(tmp_path, monkeypatch, synthetic_run):
    monkeypatch.setenv("MUJOCO_GL", "egl")
    result = render_calibration_run(
        board_directory=synthetic_run / "board",
        output_directory=tmp_path / "render-run",
        width=640,
        height=480,
    )

    payload = json.loads(result.truth_path.read_text())
    assert len(result.frame_paths) >= 12
    assert len({frame["rgb_sha256"] for frame in payload["frames"]}) == len(result.frame_paths)
    assert all(frame["assessment"]["accepted"] for frame in payload["frames"])
    assert all(frame["camera_matrix"][2] == [0.0, 0.0, 1.0] for frame in payload["frames"])
    assert all(frame["board_visible_corner_count"] == 4 for frame in payload["frames"])
    assert payload["camera_parent"] == "P05_fixed_eye_in_hand"
