"""Validate newly converted meshes and FK against actual UI STEP placements.

Run in the converter Pixi environment. No Onshape connection is required.
"""

import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import trimesh
from pg3_states import joint_states, opening_mm
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parent


def origin(element):
    result = np.eye(4)
    if element is not None:
        result[:3, 3] = np.fromstring(element.get("xyz", "0 0 0"), sep=" ")
        result[:3, :3] = Rotation.from_euler(
            "xyz", np.fromstring(element.get("rpy", "0 0 0"), sep=" ")
        ).as_matrix()
    return result


def fk(robot, values):
    joints = robot.findall("joint")
    children = [joint.find("child").get("link") for joint in joints]
    roots = {link.get("name") for link in robot.findall("link")} - set(children)
    assert roots == {"base_link"} and len(children) == len(set(children))
    result = {"base_link": np.eye(4)}
    pending = list(joints)
    while pending:
        old = len(pending)
        for joint in pending[:]:
            parent = joint.find("parent").get("link")
            if parent not in result:
                continue
            motion = np.eye(4)
            if joint.get("type") != "fixed":
                axis = np.fromstring(joint.find("axis").get("xyz"), sep=" ")
                value = values[joint.get("name")]
                if joint.get("type") == "prismatic":
                    motion[:3, 3] = axis * value
                else:
                    motion[:3, :3] = Rotation.from_rotvec(axis * value).as_matrix()
            result[joint.find("child").get("link")] = (
                result[parent] @ origin(joint.find("origin")) @ motion
            )
            pending.remove(joint)
        assert len(pending) < old, "Disconnected or cyclic tree"
    return result


def compare_native(robot, native):
    cases = []
    for case in native["cases"]:
        active = {
            key: math.radians(value) for key, value in case["expected_deg"].items()
        }
        values = joint_states(90 - math.degrees(active["gripper_drive"]))
        values.update(active)
        poses = fk(robot, values)
        errors = {}
        for link in robot.findall("link"):
            visual = link.find("visual")
            if visual is None:
                continue
            name = link.get("name")
            member = case["instances"][name]
            # A representative matrix is valid only after checking every member.
            assert member["max_member_rotation_element_delta"] < 2e-5
            assert member["max_member_translation_delta_mm"] / 1000 < 2e-5
            observed = np.asarray(member["transform_m"]).reshape(4, 4)
            computed = poses[name] @ origin(visual.find("origin"))
            errors[name] = {
                "translation_m": float(
                    np.linalg.norm(computed[:3, 3] - observed[:3, 3])
                ),
                "rotation_rad": float(
                    Rotation.from_matrix(
                        computed[:3, :3].T @ observed[:3, :3]
                    ).magnitude()
                ),
            }
        assert len(errors) == 12
        maximum_t = max(x["translation_m"] for x in errors.values())
        maximum_r = max(x["rotation_rad"] for x in errors.values())
        assert maximum_t < 2e-5 and maximum_r < 2e-5, (case["name"], errors)
        cases.append(
            {
                "case": case["name"],
                "step_sha256": case["step_sha256"],
                "max_translation_m": maximum_t,
                "max_rotation_rad": maximum_r,
                "per_link": errors,
            }
        )
    assert len(cases) == 11
    return cases


def validate():
    model = ROOT / "model"
    robot = ET.parse(model / "robot.urdf").getroot()
    report = json.loads((model / "conversion.json").read_text())
    assert (
        report["input_sha256"]
        == hashlib.sha256(
            (ROOT.parent / "CAD/final-version.step").read_bytes()
        ).hexdigest()
    )
    assert report["occurrences"] == 262
    assert len(robot.findall("link")) == 16 and len(robot.findall("joint")) == 15
    zero = fk(robot, joint_states(90))
    mesh_results = {}
    all_bounds = []
    identity_error = 0.0
    for link in robot.findall("link"):
        visual = link.find("visual")
        if visual is None:
            continue
        path = model / visual.find("geometry/mesh").get("filename")
        mesh = trimesh.load_mesh(path, process=False)
        assert len(mesh.faces) > 0 and np.isfinite(mesh.vertices).all()
        name = link.get("name")
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest()
            == report["meshes"][name]["sha256"]
        )
        transform = zero[name] @ origin(visual.find("origin"))
        identity_error = max(identity_error, float(np.abs(transform - np.eye(4)).max()))
        vertices = trimesh.transform_points(mesh.vertices, transform)
        all_bounds.append([vertices.min(axis=0), vertices.max(axis=0)])
        mesh_results[name] = {
            "triangles": len(mesh.faces),
            "path": str(path.relative_to(ROOT)),
        }
    assert len(mesh_results) == 12 and identity_error < 2e-5
    bounds = [
        np.min(np.asarray(all_bounds)[:, 0], axis=0),
        np.max(np.asarray(all_bounds)[:, 1], axis=0),
    ]
    assert 0.2 < max(bounds[1] - bounds[0]) < 0.7
    residual = 0.0
    for theta in np.linspace(25, 135, 441):
        values = joint_states(float(theta))
        poses = fk(robot, values)
        for joint in robot.findall("joint"):
            limit = joint.find("limit")
            if limit is not None:
                tolerance = 1e-5 if joint.get("type") == "revolute" else 1e-8
                assert (
                    float(limit.get("lower")) - tolerance
                    <= values[joint.get("name")]
                    <= float(limit.get("upper")) + tolerance
                )
        for side in ("left", "right"):
            residual = max(
                residual,
                float(
                    np.linalg.norm(
                        poses[f"closing_{side}_1"][:3, 3]
                        - poses[f"closing_{side}_2"][:3, 3]
                    )
                ),
            )
    assert residual < 1e-6
    native = json.loads(
        (ROOT.parent / "reports/native-pose-transforms.json").read_text()
    )
    cases = compare_native(robot, native)
    result = {
        "status": "PASS_KINEMATIC_ONLY",
        "input_sha256": report["input_sha256"],
        "links": 16,
        "joints": 15,
        "actuated_joints": 5,
        "passive_joints": 4,
        "fixed_joints": 6,
        "mesh_links": 12,
        "occurrences": 262,
        "sampled_configurations": 441,
        "max_closure_error_m": residual,
        "max_zero_pose_matrix_error": identity_error,
        "native_pose_cases": len(cases),
        "native_max_translation_m": max(x["max_translation_m"] for x in cases),
        "native_max_rotation_rad": max(x["max_rotation_rad"] for x in cases),
        "native_pose_results": cases,
        "bounds_m": [x.tolist() for x in bounds],
        "meshes": mesh_results,
        "opening_mm": {str(t): opening_mm(t) for t in (25, 90, 135)},
        "limitations": [
            "Kinematics only; no validated effort/velocity, mass or inertia",
            "PG3 nonlinear coupling requires pg3_states.py; no linear mimic substitute",
            "No hardware calibration, printed fatigue test or continuous all-arm collision proof",
            "55 source sheets; collision STL need not be watertight or convex",
        ],
    }
    (ROOT / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"meshes", "native_pose_results"}
            },
            indent=2,
        )
    )
    return result


if __name__ == "__main__":
    validate()
