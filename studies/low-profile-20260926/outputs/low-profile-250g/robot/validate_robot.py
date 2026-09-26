"""Fail-closed, offline validation of the frozen low-profile V2 robot.

--model accepts a fresh converter output separately from the frozen evidence.
Reports are opt-in and never overwritten. This is not fabrication approval,
dynamics validation, a new OCCT8 conversion, or a live Onshape inspection.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path, PurePosixPath

import numpy as np
import trimesh
from pg3_states import joint_states, opening_mm
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parent
VERSION_ID = "f6162b4adc88af9d07f1194a"
FINAL_STEP_SHA256 = "9f58c947753e9229b30939da23ce4c87c1cc85eeb39372518de4ffb98991b93f"
POSE_TOL = 2e-5  # Original metres/radians acceptance criteria.
CLOSURE_TOL = 1e-6  # Original metre acceptance criterion.
SERIALIZATION_TOL = 1e-9  # Data structure/serialization check, not physical accuracy.
ACTIVE = ("joint1_yaw", "joint2_shoulder", "joint3_elbow", "joint4_wrist", "gripper_drive")
CASE_NAMES = (
    "zero",
    "small_joint1_yaw",
    "small_joint2_shoulder",
    "small_joint3_elbow",
    "small_joint4_wrist",
    "small_gripper_drive",
    "wrist_lower",
    "wrist_upper",
    "gripper_open",
    "gripper_closed",
    "restored_mid",
)


class ValidationError(ValueError):
    """Invalid/incomplete evidence; unlike assert, remains active with python -O."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_json(path):
    """Reject duplicate keys and non-standard NaN/Infinity in source evidence."""

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValidationError(f"Non-finite JSON number: {value}")

    return json.loads(
        Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite
    )


def number(value, label):
    require(not isinstance(value, bool), f"{label}: boolean is not a number")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValidationError(f"{label}: invalid number") from error
    require(math.isfinite(result), f"{label}: non-finite number")
    return result


def vector(value, label):
    items = value.split() if isinstance(value, str) else value
    require(
        isinstance(items, (list, tuple, np.ndarray)) and len(items) == 3,
        f"{label}: expected exactly three numbers",
    )
    return np.array([number(item, label) for item in items])


def rigid_matrix(value, label):
    try:
        matrix = np.asarray(value, dtype=float).reshape(4, 4)
    except (ValueError, TypeError) as error:
        raise ValidationError(f"{label}: expected a 4x4 matrix") from error
    require(np.isfinite(matrix).all(), f"{label}: non-finite matrix")
    require(
        np.allclose(matrix[3], [0, 0, 0, 1], atol=SERIALIZATION_TOL, rtol=0),
        f"{label}: invalid homogeneous bottom row",
    )
    rotation = matrix[:3, :3]
    require(
        np.allclose(rotation.T @ rotation, np.eye(3), atol=SERIALIZATION_TOL, rtol=0)
        and abs(np.linalg.det(rotation) - 1) <= SERIALIZATION_TOL,
        f"{label}: rotation must be proper orthonormal (no scale/reflection)",
    )
    return matrix


def origin(element):
    result = np.eye(4)
    if element is not None:
        result[:3, 3] = vector(element.get("xyz", "0 0 0"), "origin xyz")
        result[:3, :3] = Rotation.from_euler(
            "xyz", vector(element.get("rpy", "0 0 0"), "origin rpy")
        ).as_matrix()
    return result


def named(elements, label):
    result = {}
    for element in elements:
        name = element.get("name")
        require(
            isinstance(name, str) and bool(name) and name not in result,
            f"{label}: missing or duplicate name {name!r}",
        )
        result[name] = element
    return result


def fk(robot, values):
    links = named(robot.findall("link"), "links")
    joints = named(robot.findall("joint"), "joints")
    children, moving = [], set()
    for name, joint in joints.items():
        require(
            joint.get("type") in {"fixed", "revolute", "prismatic"},
            f"{name}: unsupported joint type for this V2 robot",
        )
        require(joint.find("mimic") is None, f"{name}: linear mimic is not PG3 coupling")
        parent, child = joint.find("parent"), joint.find("child")
        require(parent is not None and child is not None, f"{name}: missing parent/child")
        require(
            parent.get("link") in links and child.get("link") in links,
            f"{name}: undeclared parent/child link",
        )
        children.append(child.get("link"))
        if joint.get("type") != "fixed":
            moving.add(name)
    require(set(links) - set(children) == {"base_link"}, "Expected one root: base_link")
    require(len(children) == len(set(children)), "Multiple parents for a child link")
    require(set(values) == moving, "Joint state names do not match all movable joints")
    for name in moving:
        value = number(values[name], name)
        joint, limit = joints[name], joints[name].find("limit")
        require(limit is not None, f"{name}: missing limits")
        lower, upper = number(limit.get("lower"), name), number(limit.get("upper"), name)
        require(lower <= upper, f"{name}: inverted limits")
        tolerance = 1e-5 if joint.get("type") == "revolute" else 1e-8
        require(lower - tolerance <= value <= upper + tolerance, f"{name}: out of limits")
    result = {"base_link": np.eye(4)}
    pending = list(joints.values())
    while pending:
        old_count = len(pending)
        for joint in pending[:]:
            parent = joint.find("parent").get("link")
            if parent not in result:
                continue
            motion = np.eye(4)
            if joint.get("type") != "fixed":
                axis_element = joint.find("axis")
                require(axis_element is not None, f"{joint.get('name')}: missing axis")
                axis = vector(axis_element.get("xyz"), "axis")
                require(abs(np.linalg.norm(axis) - 1) <= SERIALIZATION_TOL, "Non-unit joint axis")
                value = number(values[joint.get("name")], "joint state")
                if joint.get("type") == "prismatic":
                    motion[:3, 3] = axis * value
                else:
                    motion[:3, :3] = Rotation.from_rotvec(axis * value).as_matrix()
            result[joint.find("child").get("link")] = (
                result[parent] @ origin(joint.find("origin")) @ motion
            )
            pending.remove(joint)
        require(len(pending) < old_count, "Disconnected or cyclic joint tree")
    require(set(result) == set(links), "Not every link is reachable")
    return result


def check_model_contract(robot, config):
    """Check semantics against the separate frozen UI-derived configuration."""
    require(
        robot.tag == "robot" and robot.get("name") == config["robot_name"],
        "Unexpected robot name or XML root",
    )
    require(
        config["length_unit"] == "m" and config["root"] == "base_link",
        "Expected the frozen SI/base_link configuration",
    )
    links, joints = named(robot.findall("link"), "links"), named(robot.findall("joint"), "joints")
    expected = {item["name"]: item for item in config["joints"]}
    require(len(links) == 16 and set(links) == set(config["links"]), "Link contract mismatch")
    require(
        len(joints) == 15 and len(expected) == 15 and set(joints) == set(expected),
        "Joint contract mismatch",
    )
    frames = {name: rigid_matrix(item["frame_m"], name) for name, item in config["links"].items()}
    for name, joint in joints.items():
        spec = expected[name]
        require(joint.find("mimic") is None, f"{name}: unexpected mimic")
        require(joint.get("type") == spec["type"], f"{name}: type differs from configuration")
        for role in ("parent", "child"):
            element = joint.find(role)
            require(
                element is not None and element.get("link") == spec[role],
                f"{name}: {role} differs from configuration",
            )
        relative = np.linalg.inv(frames[spec["parent"]]) @ frames[spec["child"]]
        require(
            np.allclose(origin(joint.find("origin")), relative, atol=SERIALIZATION_TOL, rtol=0),
            f"{name}: origin differs from frozen configuration",
        )
        if spec["type"] != "fixed":
            axis, limit = joint.find("axis"), joint.find("limit")
            require(axis is not None and limit is not None, f"{name}: missing axis/limit")
            require(
                np.allclose(
                    vector(axis.get("xyz"), name),
                    vector(spec["axis"], name),
                    atol=SERIALIZATION_TOL,
                    rtol=0,
                ),
                f"{name}: axis contract mismatch",
            )
            for field in ("lower", "upper", "effort", "velocity"):
                require(
                    abs(number(limit.get(field), f"{name}/{field}") - spec["limit"][field])
                    <= SERIALIZATION_TOL,
                    f"{name}: {field} differs from configuration",
                )
    return links


def compare_native(robot, native, evidence_root=None):
    evidence = Path(evidence_root) if evidence_root is not None else ROOT.parent
    groups = load_json(evidence / "reports/expected-groups.json")["groups"]
    targets_list = load_json(evidence / "reports/native-pose-targets.json")["cases"]
    targets = {case["name"]: case["expected_deg"] for case in targets_list}
    require(len(targets_list) == 11 and set(targets) == set(CASE_NAMES), "Invalid target pose set")
    require(native["baseline_version"] == VERSION_ID, "Native evidence is not the frozen V2")
    require(len(native["cases"]) == 11, "Expected all 11 native poses")
    names = [case["name"] for case in native["cases"]]
    require(
        len(set(names)) == 11 and set(names) == set(targets), "Duplicate, missing or unknown pose"
    )
    require(
        set(named(robot.findall("link"), "links"))
        == set(load_json(evidence / "robot/converter-config.json")["links"]),
        "Native link set differs",
    )
    geometric = {
        link.get("name"): link for link in robot.findall("link") if link.find("visual") is not None
    }
    require(
        set(geometric) == set(groups) and len(groups) == 12, "Expected exactly 12 geometric links"
    )
    cases = []
    for case in native["cases"]:
        name = case["name"]
        require(set(case["expected_deg"]) == set(ACTIVE), f"{name}: missing/extra active target")
        for key in ACTIVE:
            require(
                abs(number(case["expected_deg"][key], key) - targets[name][key])
                <= SERIALIZATION_TOL,
                f"{name}/{key}: target was changed",
            )
        require(set(case["instances"]) == set(groups), f"{name}: missing/extra rigid group")
        active = {
            key: math.radians(number(value, key)) for key, value in case["expected_deg"].items()
        }
        values = joint_states(90 - math.degrees(active["gripper_drive"]))
        values.update(active)
        poses = fk(robot, values)
        errors = {}
        for link_name, link in geometric.items():
            member = case["instances"][link_name]
            require(
                type(member["body_count"]) is int
                and member["body_count"] == len(groups[link_name]),
                f"{name}/{link_name}: body count mismatch",
            )
            for field, scale in (
                ("max_member_rotation_element_delta", 1),
                ("max_member_translation_delta_mm", 0.001),
            ):
                delta = number(member[field], f"{name}/{link_name}/{field}")
                require(
                    0 <= delta * scale < POSE_TOL, f"{name}/{link_name}: member rigidity failure"
                )
            observed = rigid_matrix(member["transform_m"], f"{name}/{link_name}")
            computed = poses[link_name] @ origin(link.find("visual/origin"))
            errors[link_name] = {
                "translation_m": float(np.linalg.norm(computed[:3, 3] - observed[:3, 3])),
                "rotation_rad": float(
                    Rotation.from_matrix(computed[:3, :3].T @ observed[:3, :3]).magnitude()
                ),
            }
        maximum_t = max(item["translation_m"] for item in errors.values())
        maximum_r = max(item["rotation_rad"] for item in errors.values())
        require(maximum_t < POSE_TOL and maximum_r < POSE_TOL, f"{name}: FK/STEP pose mismatch")
        observed_angles = case["observed_from_step_deg"]
        require(set(observed_angles) == set(ACTIVE), f"{name}: incomplete observed angles")
        for key in ACTIVE:
            require(
                abs(math.radians(number(observed_angles[key], key) - targets[name][key]))
                < POSE_TOL,
                f"{name}/{key}: observed active angle mismatch",
            )
        path = evidence / "CAD/native-poses" / f"{name}.step"
        require(case["step_sha256"] == sha256(path), f"{name}: native STEP hash mismatch")
        cases.append(
            {
                "case": name,
                "step_sha256": case["step_sha256"],
                "max_translation_m": maximum_t,
                "max_rotation_rad": maximum_r,
                "per_link": errors,
            }
        )
    return cases


def local_mesh_path(model, filename):
    require(isinstance(filename, str) and bool(filename), "Missing mesh filename")
    relative = PurePosixPath(filename)
    require(
        not relative.is_absolute()
        and ".." not in relative.parts
        and "\\" not in filename
        and ":" not in filename,
        "Mesh path must be local and relative",
    )
    path = (model / relative).resolve()
    require(path.is_relative_to(model.resolve()), "Mesh symlink escapes the model directory")
    require(path.is_file(), f"Mesh file missing: {filename}")
    return path


def mesh_filename(element):
    geometry = element.find("geometry")
    require(
        geometry is not None and len(geometry) == 1 and geometry[0].tag == "mesh",
        "Expected exactly one mesh geometry",
    )
    mesh = geometry[0]
    require(
        np.allclose(
            vector(mesh.get("scale", "1 1 1"), "mesh scale"),
            np.ones(3),
            atol=SERIALIZATION_TOL,
            rtol=0,
        ),
        "Unexpected mesh scale (expected SI)",
    )
    return mesh.get("filename")


def validate(model_dir=None, evidence_root=None, native_file=None):
    model = Path(model_dir).resolve() if model_dir is not None else ROOT / "model"
    evidence = Path(evidence_root).resolve() if evidence_root is not None else ROOT.parent
    native_path = (
        Path(native_file)
        if native_file is not None
        else evidence / "reports/native-pose-transforms.json"
    )
    robot = ET.parse(model / "robot.urdf").getroot()
    report = load_json(model / "conversion.json")
    config = load_json(evidence / "robot/converter-config.json")
    require(
        load_json(model / "config.json") == config, "Converted config differs from frozen input"
    )
    require(
        report["input_sha256"] == sha256(evidence / "CAD/final-version.step") == FINAL_STEP_SHA256,
        "Final V2 input STEP hash mismatch",
    )
    require(
        report["occurrences"] == 262 and report["links"] == 16 and report["joints"] == 15,
        "Conversion counts differ from V2 contract",
    )
    require(
        report["reader_unit"] == "mm" and report["mesh_and_urdf_unit"] == "m",
        "Conversion unit mismatch",
    )
    links = check_model_contract(robot, config)
    groups = load_json(evidence / "reports/expected-groups.json")["groups"]
    require(set(report["meshes"]) == set(groups), "Mesh report has missing/extra groups")
    indices = []
    for name, mesh in report["meshes"].items():
        expected_names = Counter(part["name"] for part in groups[name])
        require(
            mesh["occurrence_names"] == expected_names, f"{name}: occurrence membership mismatch"
        )
        require(
            len(mesh["occurrence_indices"])
            == len(groups[name])
            == config["links"][name]["expected_occurrences"],
            f"{name}: occurrence count mismatch",
        )
        indices.extend(mesh["occurrence_indices"])
    require(
        all(type(index) is int for index in indices) and sorted(indices) == list(range(262)),
        "Every occurrence index must be assigned exactly once",
    )
    zero = fk(robot, joint_states(90))
    mesh_results, all_bounds = {}, []
    identity_error = 0.0
    for name, link in links.items():
        visuals, collisions = link.findall("visual"), link.findall("collision")
        if name not in groups:
            require(not visuals and not collisions, f"{name}: cut frame unexpectedly has geometry")
            continue
        require(len(visuals) == len(collisions) == 1, f"{name}: need one visual and collision")
        visual, collision = visuals[0], collisions[0]
        filename = mesh_filename(visual)
        require(
            filename == mesh_filename(collision) == report["meshes"][name]["path"],
            f"{name}: visual/collision mesh differs from report",
        )
        require(
            np.allclose(
                origin(visual.find("origin")),
                origin(collision.find("origin")),
                atol=SERIALIZATION_TOL,
                rtol=0,
            ),
            f"{name}: collision origin differs",
        )
        path = local_mesh_path(model, filename)
        require(sha256(path) == report["meshes"][name]["sha256"], f"{name}: mesh hash mismatch")
        mesh = trimesh.load_mesh(path, process=False)
        require(
            isinstance(mesh, trimesh.Trimesh)
            and len(mesh.faces) > 0
            and np.isfinite(mesh.vertices).all(),
            f"{name}: invalid or empty mesh",
        )
        transform = zero[name] @ origin(visual.find("origin"))
        identity_error = max(identity_error, float(np.abs(transform - np.eye(4)).max()))
        vertices = trimesh.transform_points(mesh.vertices, transform)
        all_bounds.append([vertices.min(axis=0), vertices.max(axis=0)])
        mesh_results[name] = {
            "triangles": len(mesh.faces),
            "path": filename,
            "sha256": sha256(path),
        }
    require(len(mesh_results) == 12 and identity_error < POSE_TOL, "Zero-pose mesh frame mismatch")
    bounds = [
        np.min(np.asarray(all_bounds)[:, 0], axis=0),
        np.max(np.asarray(all_bounds)[:, 1], axis=0),
    ]
    require(0.2 < max(bounds[1] - bounds[0]) < 0.7, "Whole-model SI bounds invalid")
    residual = 0.0
    for theta in np.linspace(25, 135, 441):
        poses = fk(robot, joint_states(float(theta)))
        for side in ("left", "right"):
            residual = max(
                residual,
                float(
                    np.linalg.norm(
                        poses[f"closing_{side}_1"][:3, 3] - poses[f"closing_{side}_2"][:3, 3]
                    )
                ),
            )
    require(residual < CLOSURE_TOL, "PG3 closure residual exceeds original tolerance")
    cases = compare_native(robot, load_json(native_path), evidence)
    return {
        "status": "PASS_KINEMATIC_ONLY",
        "fabrication_approved": False,
        "input_sha256": report["input_sha256"],
        "model_directory": model.relative_to(evidence).as_posix()
        if model.is_relative_to(evidence)
        else model.name,
        "urdf_sha256": sha256(model / "robot.urdf"),
        "config_sha256": sha256(evidence / "robot/converter-config.json"),
        "native_evidence_sha256": sha256(native_path),
        "validator_sha256": sha256(Path(__file__)),
        "runtime": {
            "python": sys.version.split()[0],
            **{name: importlib.metadata.version(name) for name in ("numpy", "scipy", "trimesh")},
        },
        "links": len(links),
        "joints": len(robot.findall("joint")),
        "actuated_joints": len(ACTIVE),
        "passive_joints": 4,
        "fixed_joints": 6,
        "mesh_links": len(mesh_results),
        "occurrences": len(indices),
        "sampled_configurations": 441,
        "max_closure_error_m": residual,
        "max_zero_pose_matrix_error": identity_error,
        "native_pose_cases": len(cases),
        "native_max_translation_m": max(case["max_translation_m"] for case in cases),
        "native_max_rotation_rad": max(case["max_rotation_rad"] for case in cases),
        "native_pose_results": cases,
        "bounds_m": [item.tolist() for item in bounds],
        "meshes": mesh_results,
        "opening_mm": {str(theta): opening_mm(theta) for theta in (25, 90, 135)},
        "thresholds": {
            "pose_translation_m": POSE_TOL,
            "pose_rotation_rad": POSE_TOL,
            "closure_m": CLOSURE_TOL,
            "structure_serialization": SERIALIZATION_TOL,
        },
        "limitations": [
            "Kinematics only; no validated effort/velocity, mass or inertia",
            "PG3 nonlinear coupling requires pg3_states.py; no linear mimic substitute",
            "No hardware calibration, printed fatigue test or continuous all-arm collision proof",
            "55 source sheets; collision STL need not be watertight or convex",
            "STEP hashes bind files, not the correctness of cached matrix extraction; use replay_step.py",
            "Validation is not a new Pixi/OCCT8 conversion or a live Onshape inspection",
        ],
    }


def write_json_exclusive(path, result):
    """Refuse an existing report instead of destroying earlier evidence."""
    path = Path(path)
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", type=Path, default=ROOT / "model", help="Fresh or archived converter output"
    )
    parser.add_argument(
        "--inputs", type=Path, default=ROOT.parent, help="Frozen low-profile-250g evidence bundle"
    )
    parser.add_argument(
        "--native", type=Path, help="Alternative freshly replayed native-pose report"
    )
    parser.add_argument(
        "--output", type=Path, help="New report file (must not exist); default: stdout only"
    )
    args = parser.parse_args(argv)
    try:
        if args.output is not None:
            require(not args.output.exists(), "Output already exists; use a new report path")
        result = validate(args.model, args.inputs, args.native)
        if args.output is not None:
            write_json_exclusive(args.output, result)
        summary = {
            key: value
            for key, value in result.items()
            if key not in {"meshes", "native_pose_results"}
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError, ET.ParseError) as error:
        print(
            json.dumps(
                {"status": "FAIL", "error_type": type(error).__name__, "error": str(error)},
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
