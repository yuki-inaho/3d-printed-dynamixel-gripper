import numpy as np
import pytest

from simulation.frames import (
    camera_intrinsics_from_fovy,
    invert_transform,
    mujoco_camera_pose,
    project_world_points,
)


def test_mujoco_camera_axes_are_converted_to_opencv_axes():
    pose = mujoco_camera_pose(np.zeros(3), np.eye(3))

    np.testing.assert_allclose(pose.world_from_camera[:3, 0], [1.0, 0.0, 0.0])
    np.testing.assert_allclose(pose.world_from_camera[:3, 1], [0.0, -1.0, 0.0])
    np.testing.assert_allclose(pose.world_from_camera[:3, 2], [0.0, 0.0, -1.0])
    assert np.linalg.det(pose.world_from_camera[:3, :3]) == pytest.approx(1.0)


def test_world_from_camera_and_camera_from_world_are_true_inverses():
    rotation_world_from_mujoco_camera = np.array(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    )
    pose = mujoco_camera_pose([0.3, -0.2, 0.7], rotation_world_from_mujoco_camera)

    np.testing.assert_allclose(
        pose.camera_from_world,
        invert_transform(pose.world_from_camera),
        atol=1e-12,
    )
    np.testing.assert_allclose(
        pose.camera_from_world @ pose.world_from_camera,
        np.eye(4),
        atol=1e-12,
    )
    assert not np.allclose(pose.camera_from_world, pose.world_from_camera.T)


def test_known_mujoco_forward_point_projects_to_image_center():
    pose = mujoco_camera_pose(np.zeros(3), np.eye(3))
    intrinsics = camera_intrinsics_from_fovy(width=640, height=480, fovy_degrees=60.0)

    pixels, depth = project_world_points(
        np.array([[0.0, 0.0, -2.0]]),
        intrinsics.matrix,
        pose.camera_from_world,
    )

    np.testing.assert_allclose(pixels[0], [320.0, 240.0], atol=1e-12)
    np.testing.assert_allclose(depth, [2.0], atol=1e-12)


def test_intrinsics_use_vertical_fovy_and_square_pixels():
    intrinsics = camera_intrinsics_from_fovy(width=640, height=480, fovy_degrees=60.0)
    expected_focal = 240.0 / np.tan(np.deg2rad(30.0))

    assert intrinsics.fx == pytest.approx(expected_focal)
    assert intrinsics.fy == pytest.approx(expected_focal)
    assert intrinsics.cx == pytest.approx(320.0)
    assert intrinsics.cy == pytest.approx(240.0)
    np.testing.assert_allclose(
        intrinsics.matrix,
        [[expected_focal, 0.0, 320.0], [0.0, expected_focal, 240.0], [0.0, 0.0, 1.0]],
    )


@pytest.mark.parametrize("bad_fovy", [0.0, -10.0, 180.0])
def test_intrinsics_reject_invalid_fovy(bad_fovy):
    with pytest.raises(ValueError, match="fovy"):
        camera_intrinsics_from_fovy(width=640, height=480, fovy_degrees=bad_fovy)


def test_projection_rejects_points_on_or_behind_camera():
    pose = mujoco_camera_pose(np.zeros(3), np.eye(3))
    intrinsics = camera_intrinsics_from_fovy(width=640, height=480, fovy_degrees=45.0)

    with pytest.raises(ValueError, match="positive OpenCV camera depth"):
        project_world_points(
            np.array([[0.0, 0.0, 1.0]]),
            intrinsics.matrix,
            pose.camera_from_world,
        )
