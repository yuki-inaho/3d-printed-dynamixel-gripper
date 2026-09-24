import json

import cv2
import pytest

from simulation.aprilgrid import AprilGridSpec, generate_aprilgrid, validate_spec


def test_aprilgrid_rejects_duplicate_and_out_of_range_ids():
    with pytest.raises(ValueError, match="unique"):
        validate_spec(AprilGridSpec(rows=1, columns=2, tag_ids=(4, 4)))

    with pytest.raises(ValueError, match="dictionary range"):
        validate_spec(AprilGridSpec(rows=1, columns=1, tag_ids=(587,)))


def test_aprilgrid_rejects_quiet_zone_in_tag_size_definition():
    with pytest.raises(ValueError, match="black border outer"):
        validate_spec(
            AprilGridSpec(
                rows=1,
                columns=1,
                tag_ids=(0,),
                tag_size_definition="including_quiet_zone",
            )
        )


def test_generated_board_pixel_pitch_corners_and_redetection(tmp_path):
    spec = AprilGridSpec(
        rows=2,
        columns=3,
        tag_ids=(10, 11, 12, 13, 14, 15),
        tag_size_mm=30.0,
        tag_spacing_mm=10.0,
        board_margin_mm=10.0,
        pixels_per_mm=4,
    )
    result = generate_aprilgrid(spec, tmp_path / "board-run")

    image = cv2.imread(str(result.png_path), cv2.IMREAD_GRAYSCALE)
    assert image.shape == (360, 520)
    assert result.board_width_mm == pytest.approx(130.0)
    assert result.board_height_mm == pytest.approx(90.0)

    payload = json.loads(result.json_path.read_text())
    first = payload["tags"][0]
    assert first["pixel_corners"] == [[40, 40], [160, 40], [160, 160], [40, 160]]
    assert first["object_corners_mm"] == [
        [10.0, 10.0, 0.0],
        [40.0, 10.0, 0.0],
        [40.0, 40.0, 0.0],
        [10.0, 40.0, 0.0],
    ]

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    corners, ids, rejected = cv2.aruco.ArucoDetector(dictionary).detectMarkers(image)
    assert rejected is not None
    assert len(corners) == 6
    assert sorted(ids.flatten().tolist()) == list(spec.tag_ids)
    assert result.mujoco_asset_path.read_text().count("DICT_APRILTAG_36h11") == 1


def test_generate_refuses_to_overwrite_existing_run(tmp_path):
    output = tmp_path / "board-run"
    output.mkdir()
    with pytest.raises(FileExistsError):
        generate_aprilgrid(AprilGridSpec(rows=1, columns=1, tag_ids=(0,)), output)
