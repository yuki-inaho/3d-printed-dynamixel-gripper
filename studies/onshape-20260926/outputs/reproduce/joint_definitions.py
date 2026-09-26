"""CAD-space kinematics, mm/degrees. Zero is the imported mid-pose, not hardware home."""

import math

X0 = math.sqrt(24**2 - 14**2)


def slide(angle):
    t = math.radians(angle)
    return 14 * math.cos(t) + math.sqrt(24**2 - (14 * math.sin(t)) ** 2) - X0


JOINTS = [
    {
        "name": "joint1_yaw",
        "a": "base_link",
        "b": "shoulder_yaw",
        "xyz": [0, 0, 20],
        "axis": "Z",
        "rot": 0,
        "type": "REVOLUTE",
    },
    {
        "name": "joint2_shoulder",
        "a": "shoulder_yaw",
        "b": "upper_arm",
        "xyz": [-0.2, 0, 56.3],
        "axis": "Y",
        "rot": -90,
        "type": "REVOLUTE",
    },
    {
        "name": "joint3_elbow",
        "a": "upper_arm",
        "b": "forearm",
        "xyz": [-0.2, 14.8, 164.6],
        "axis": "Y",
        "rot": 90,
        "type": "REVOLUTE",
    },
    {
        "name": "joint4_wrist",
        "a": "forearm",
        "b": "wrist",
        "xyz": [-0.2, 104.9, 164.6],
        "axis": "Y",
        "rot": 90,
        "type": "REVOLUTE",
        "limits": [-110, 138],
    },
    {
        "name": "gripper_drive",
        "a": "wrist",
        "b": "gripper_crank",
        "xyz": [-0.2, 164.9, 164.6],
        "axis": "X",
        "rot": -90,
        "type": "REVOLUTE",
        "limits": [-45, 65],
    },
    {
        "name": "jaw_left",
        "a": "wrist",
        "b": "jaw_l",
        "xyz": [-0.2, 164.9, 164.6],
        "axis": "Y",
        "rot": 90,
        "type": "SLIDER",
        "limits": [slide(135), slide(25)],
    },
    {
        "name": "jaw_right",
        "a": "wrist",
        "b": "jaw_r",
        "xyz": [-0.2, 164.9, 164.6],
        "axis": "Y",
        "rot": 90,
        "type": "SLIDER",
        "limits": [-slide(25), -slide(135)],
    },
    {
        "name": "coupler_left",
        "a": "gripper_crank",
        "b": "coupler_l",
        "xyz": [-0.2, 164.9, 178.6],
        "axis": "X",
        "rot": -90,
        "type": "REVOLUTE",
    },
    {
        "name": "coupler_right",
        "a": "gripper_crank",
        "b": "coupler_r",
        "xyz": [-0.2, 164.9, 150.6],
        "axis": "X",
        "rot": -90,
        "type": "REVOLUTE",
    },
    {
        "name": "camera_mount_fixed",
        "a": "wrist",
        "b": "camera_mount",
        "xyz": [-0.2, 164.9, 199.85],
        "axis": "Z",
        "rot": 0,
        "type": "FASTENED",
    },
    {
        "name": "camera_body_fixed",
        "a": "camera_mount",
        "b": "camera_body",
        "xyz": [-0.2, 197, 257],
        "axis": "Z",
        "rot": 0,
        "type": "FASTENED",
    },
    {
        "name": "closing_left",
        "a": "coupler_l",
        "b": "jaw_l",
        "xyz": [-0.2 - X0, 192.9, 164.6],
        "axis": "X",
        "rot": -90,
        "type": "BALL",
        "closing": True,
    },
    {
        "name": "closing_right",
        "a": "coupler_r",
        "b": "jaw_r",
        "xyz": [-0.2 + X0, 192.9, 164.6],
        "axis": "X",
        "rot": -90,
        "type": "BALL",
        "closing": True,
    },
]
