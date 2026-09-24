import json
import shutil

import cv2
import numpy as np

from simulation.detect_aprilgrid import (
    detect_calibration_run,
    detect_frame,
    validate_detection,
)


def _truth(render_run):
    return json.loads((render_run / "ground_truth.json").read_text())


def test_normal_render_detects_all_tags_and_uses_measured_corners(render_run):
    truth = _truth(render_run)
    image = cv2.imread(str(render_run / "frame_00.png"), cv2.IMREAD_GRAYSCALE)
    detection = detect_frame(image, truth["tag_corners_world_m"])

    assert detection["accepted"] is True
    assert detection["tag_count"] == 12
    assert detection["corner_count"] == 48
    assert sorted(item["id"] for item in detection["tags"]) == list(range(12))
    projected_truth = np.asarray(truth["frames"][0]["projected_board_corners_px"])
    measured_tag_corner = np.asarray(detection["tags"][0]["image_corners_px"])[0]
    assert not np.allclose(measured_tag_corner, projected_truth[0])


def test_blur_occlusion_and_wrong_dictionary_are_rejected(render_run):
    truth = _truth(render_run)
    image = cv2.imread(str(render_run / "frame_00.png"), cv2.IMREAD_GRAYSCALE)
    blurred = cv2.GaussianBlur(image, (81, 81), 30)
    occluded = image.copy()
    occluded[100:400, 100:550] = 0

    assert detect_frame(blurred, truth["tag_corners_world_m"])["accepted"] is False
    assert detect_frame(occluded, truth["tag_corners_world_m"])["accepted"] is False
    wrong = detect_frame(
        image,
        truth["tag_corners_world_m"],
        dictionary_name="DICT_4X4_50",
    )
    assert wrong["accepted"] is False
    assert wrong["reason"] == "zero_detections"


def test_duplicate_ids_and_boundary_cut_are_rejected():
    corners = [
        np.array([[10, 10], [20, 10], [20, 20], [10, 20]], dtype=float),
        np.array([[30, 30], [40, 30], [40, 40], [30, 40]], dtype=float),
    ]
    duplicate = validate_detection([1, 1], corners, (100, 100), {1, 2})
    assert duplicate == (False, "duplicate_ids")

    cut = validate_detection([1, 2], [corners[0], corners[1] - 30], (100, 100), {1, 2})
    assert cut == (False, "corner_on_image_boundary")


def test_run_writes_all_detection_records_and_overlays(tmp_path, render_run):
    result = detect_calibration_run(render_run, tmp_path / "detections")
    payload = json.loads(result.json_path.read_text())

    assert len(payload["frames"]) == 12
    assert all(frame["accepted"] for frame in payload["frames"])
    assert all(frame["tag_count"] >= 2 for frame in payload["frames"])
    assert len(result.overlay_paths) == 12


def test_corrupt_frame_is_preserved_as_rejected_record(tmp_path, render_run):
    corrupt_render = tmp_path / "corrupt-render"
    shutil.copytree(render_run, corrupt_render)
    frame = corrupt_render / "frame_03.png"
    image = cv2.imread(str(frame), cv2.IMREAD_COLOR)
    image[:] = 0
    assert cv2.imwrite(str(frame), image)

    result = detect_calibration_run(corrupt_render, tmp_path / "detections")
    payload = json.loads(result.json_path.read_text())

    assert len(payload["frames"]) == 12
    assert payload["accepted_frame_count"] == 11
    assert payload["rejected_frames"] == [{"frame_index": 3, "reason": "source_rgb_sha_mismatch"}]


def test_renderer_rejection_cannot_be_promoted_by_tag_detection(tmp_path, render_run):
    copied = tmp_path / "renderer-rejected"
    shutil.copytree(render_run, copied)
    path = copied / "ground_truth.json"
    truth = json.loads(path.read_text())
    truth["frames"][0]["assessment"].update(accepted=False, reason="duplicate_frame")
    path.write_text(json.dumps(truth))
    result = detect_calibration_run(copied, tmp_path / "detections")
    payload = json.loads(result.json_path.read_text())
    assert payload["accepted_frame_count"] == 11
    assert payload["rejected_frames"][0]["reason"] == "renderer_rejected:duplicate_frame"
