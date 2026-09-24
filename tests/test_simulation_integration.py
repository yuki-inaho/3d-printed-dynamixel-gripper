import numpy as np
import pytest

from simulation.integration import (
    candidate_camera_pose_from_spec,
    horn_following_camera_pose,
    mujoco_pose_from_opencv_pose,
    p05_fixed_camera_pose,
)


def test_p05_camera_does_not_inherit_j5_roll():
    base = candidate_camera_pose_from_spec()
    at_zero = p05_fixed_camera_pose(base, j5_roll_degrees=0.0)
    at_ninety = p05_fixed_camera_pose(base, j5_roll_degrees=90.0)

    np.testing.assert_allclose(at_zero, at_ninety, atol=1e-12)


def test_rejected_horn_mount_inherits_j5_roll():
    base = candidate_camera_pose_from_spec()
    at_zero = horn_following_camera_pose(base, j5_roll_degrees=0.0)
    at_ninety = horn_following_camera_pose(base, j5_roll_degrees=90.0)

    assert not np.allclose(at_zero, at_ninety)
    assert np.linalg.norm(at_zero[:3, 3] - at_ninety[:3, 3]) > 0.01


def test_candidate_optical_axis_and_mujoco_conversion_are_right_handed():
    opencv_pose = candidate_camera_pose_from_spec()
    mujoco_pose = mujoco_pose_from_opencv_pose(opencv_pose)

    expected_optical_axis = np.array([0.0, np.sqrt(3.0) / 2.0, -0.5])
    np.testing.assert_allclose(opencv_pose[:3, 2], expected_optical_axis, atol=1e-12)
    np.testing.assert_allclose(mujoco_pose[:3, 2], -expected_optical_axis, atol=1e-12)
    assert np.linalg.det(opencv_pose[:3, :3]) == pytest.approx(1.0)
    assert np.linalg.det(mujoco_pose[:3, :3]) == pytest.approx(1.0)


def test_coordinate_reflection_is_rejected():
    reflected = np.eye(4)
    reflected[0, 0] = -1.0
    with pytest.raises(ValueError, match="right-handed"):
        mujoco_pose_from_opencv_pose(reflected)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_pose_translation_is_rejected(bad):
    pose = np.eye(4)
    pose[0, 3] = bad
    with pytest.raises(ValueError):
        mujoco_pose_from_opencv_pose(pose)


def test_actual_mujoco_joint_camera_and_parent_transform():
    import mujoco

    from simulation.frames import mujoco_camera_pose
    from simulation.integration import build_camera_rig

    candidate = candidate_camera_pose_from_spec()
    parent = np.eye(4)
    parent[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
    parent[:3, 3] = [0.1, -0.2, 0.3]
    model = build_camera_rig(candidate, world_from_reference=parent)
    data = mujoco.MjData(model)
    fixed_id = model.camera("p05_camera").id
    horn_id = model.camera("horn_negative").id
    assert model.body(model.cam_bodyid[fixed_id]).name == "P05"
    assert model.body(model.cam_bodyid[horn_id]).name == "J5_output"
    measured = []
    horn = []
    for angle in (0, 0.4, 1.2):
        data.qpos[model.joint("J5").qposadr[0]] = angle
        mujoco.mj_forward(model, data)
        measured.append(
            mujoco_camera_pose(
                data.cam_xpos[fixed_id], data.cam_xmat[fixed_id].reshape(3, 3)
            ).world_from_camera
        )
        horn.append(data.cam_xpos[horn_id].copy())
    for pose in measured:
        np.testing.assert_allclose(pose, parent @ candidate, atol=1e-10)
    assert np.linalg.norm(horn[0] - horn[-1]) > 0.01
