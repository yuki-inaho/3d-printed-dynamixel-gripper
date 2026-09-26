"""Validate kinematic topology, meshes, exported frame closure and native poses.
Requires numpy and trimesh; run from any cwd. No Onshape credentials needed.
"""

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import trimesh
from pg3_states import joint_states, opening_mm

ROOT = Path(__file__).resolve().parent


def rotation(axis, angle):
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    x, y, z = axis
    K = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) + math.sin(angle) * K + (1 - math.cos(angle)) * (K @ K)


def origin(el):
    T = np.eye(4)
    if el is None:
        return T
    r, p, y = map(float, el.get("rpy", "0 0 0").split())
    T[:3, :3] = rotation([0, 0, 1], y) @ rotation([0, 1, 0], p) @ rotation([1, 0, 0], r)
    T[:3, 3] = list(map(float, el.get("xyz", "0 0 0").split()))
    return T


def fk(robot, q):
    joints = robot.findall("joint")
    children = [j.find("child").get("link") for j in joints]
    roots = {l.get("name") for l in robot.findall("link")} - set(children)
    assert roots == {"base_link"}, roots
    assert len(children) == len(set(children)), "multiple parents"
    poses = {"base_link": np.eye(4)}
    pending = list(joints)
    while pending:
        old = len(pending)
        for j in pending[:]:
            parent = j.find("parent").get("link")
            child = j.find("child").get("link")
            if parent not in poses:
                continue
            motion = np.eye(4)
            val = q.get(j.get("name"), 0)
            axis = (
                list(map(float, j.find("axis").get("xyz").split()))
                if j.find("axis") is not None
                else [0, 0, 1]
            )
            if j.get("type") in ["revolute", "continuous"]:
                motion[:3, :3] = rotation(axis, val)
            elif j.get("type") == "prismatic":
                motion[:3, 3] = np.array(axis) * val
            poses[child] = poses[parent] @ origin(j.find("origin")) @ motion
            pending.remove(j)
        assert len(pending) < old, "cycle or disconnected joint"
    return poses


def validate():
    robot = ET.parse(ROOT / "robot.urdf").getroot()
    q0 = joint_states(90)
    poses = fk(robot, q0)
    meshes = {}
    bounds = []
    max_identity_error = 0
    for l in robot.findall("link"):
        v = l.find("visual")
        if v is None:
            continue
        m = ROOT / v.find("geometry/mesh").get("filename")
        assert m.is_file(), m
        mesh = trimesh.load_mesh(m, process=False)
        assert np.isfinite(mesh.vertices).all()
        T = poses[l.get("name")] @ origin(v.find("origin"))
        # Exported mesh vertices use the original CAD world frame.
        max_identity_error = max(
            max_identity_error, float(np.max(np.abs(T - np.eye(4))))
        )
        b = trimesh.transform_points(mesh.vertices, T)
        bounds.append([b.min(axis=0), b.max(axis=0)])
        meshes[l.get("name")] = {
            "triangles": len(mesh.faces),
            "path": str(m.relative_to(ROOT)),
        }
    assert len(meshes) == 12
    lo = np.min(np.array(bounds)[:, 0, :], axis=0)
    hi = np.max(np.array(bounds)[:, 1, :], axis=0)
    assert 0.2 < max(hi - lo) < 0.7, "unexpected CAD unit/scale"
    residual = 0.0
    samples = []
    for theta in np.linspace(25, 135, 441):
        q = joint_states(float(theta))
        p = fk(robot, q)
        for j in robot.findall("joint"):
            lim = j.find("limit")
            if lim is not None:
                value = q[j.get("name")]
                # Exporter serializes quantities with six significant digits.
                tol = 1e-5 if j.get("type") == "revolute" else 1e-8
                assert (
                    float(lim.get("lower")) - tol
                    <= value
                    <= float(lim.get("upper")) + tol
                ), (theta, j.get("name"), value)
        for side in ["left", "right"]:
            err = float(
                np.linalg.norm(
                    p[f"closing_{side}_1"][:3, 3] - p[f"closing_{side}_2"][:3, 3]
                )
            )
            residual = max(residual, err)
        if theta in [25, 90, 135]:
            samples.append(
                {
                    "theta_deg": float(theta),
                    "opening_mm": opening_mm(theta),
                    "joint_positions": q,
                }
            )
    assert residual < 1e-6, residual
    assert max_identity_error < 2e-5, max_identity_error
    native = json.loads((ROOT / "native-reference.json").read_text())
    native_results = []
    for case in native["cases"]:
        active = case["active_positions_rad"]
        q = joint_states(90 - math.degrees(active["gripper_drive"]))
        q.update(active)
        p = fk(robot, q)
        errors = {}
        for link in robot.findall("link"):
            visual = link.find("visual")
            if visual is None:
                continue
            name = link.get("name")
            computed = p[name] @ origin(visual.find("origin"))
            observed = np.array(case["occurrence_matrices"][name]).reshape(4, 4)
            errors[name] = float(np.max(np.abs(computed - observed)))
        assert len(errors) == 12
        assert max(errors.values()) < 2e-5, (case["case"], errors)
        native_results.append(
            {
                "case": case["case"],
                "max_matrix_error": max(errors.values()),
                "per_link_error": errors,
            }
        )
    assert len(native_results) == 11
    assert len(robot.findall("link")) == 16 and len(robot.findall("joint")) == 15
    report = {
        "status": "PASS_KINEMATIC_ONLY",
        "links": len(robot.findall("link")),
        "joints": len(robot.findall("joint")),
        "actuated_joints": 5,
        "passive_joints": 4,
        "fixed_joints": 6,
        "mesh_links": 12,
        "sampled_configurations": 441,
        "max_closure_error_m": residual,
        "native_pose_cases": len(native_results),
        "native_max_matrix_error": max(r["max_matrix_error"] for r in native_results),
        "native_pose_results": native_results,
        "max_zero_pose_matrix_error": max_identity_error,
        "bounds_m": [lo.tolist(), hi.tolist()],
        "meshes": meshes,
        "samples": samples,
        "limitations": [
            "No measured mass/inertia or effort/velocity limits",
            "No hardware homing/calibration",
            "Nonlinear coupling supplied by pg3_states.py, not encoded as URDF mimic",
            "No whole-arm continuous collision validation",
            "Motor M01-M04 visuals retain unsplit supplier bodies",
        ],
    }
    (ROOT / "validation.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in ["meshes", "samples", "native_pose_results"]
            },
            indent=2,
        )
    )
    return robot, report


if __name__ == "__main__":
    validate()
