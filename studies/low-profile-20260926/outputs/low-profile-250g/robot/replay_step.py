"""Re-read the frozen V2 and its 11 archived native STEP poses, offline.

This independent CadQuery/OCP audit is not a new OCCT8 STEP-to-URDF conversion.
Every occurrence is checked; saved native-step JSON files are not the input.
Partial inventories and a FAIL report remain available when a check fails.
"""

import argparse
import importlib.metadata
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from validate_robot import (
    ACTIVE,
    CASE_NAMES,
    FINAL_STEP_SHA256,
    POSE_TOL,
    ROOT,
    VERSION_ID,
    load_json,
    require,
    rigid_matrix,
    sha256,
    write_json_exclusive,
)


def assembly_reader():
    """Find the included reader by repository markers, not a former PC's path."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "scripts/assembly_io.py").is_file() and (parent / "AGENTS.md").is_file():
            sys.path.insert(0, str(parent))
            from scripts.assembly_io import bounds, read_step

            return read_step, bounds, parent / "scripts/assembly_io.py"
    raise ValueError(
        "Include repository scripts/assembly_io.py and AGENTS.md when relocating this tool"
    )


def inventory(path, read_step, bounds):
    """Record every occurrence's name, body type, local geometry bounds and placement."""
    before = sha256(path)
    doc, tool, rows = read_step(path)
    parts = []
    for row in rows:
        transform = row.loc.wrapped.Transformation()
        matrix = np.eye(4)
        matrix[:3] = [[transform.Value(i, j) for j in range(1, 5)] for i in range(1, 4)]
        rigid_matrix(matrix, f"{path.name}/{row.index}")
        local_bounds = bounds(row.shape)
        require(np.isfinite(local_bounds).all(), f"{path.name}: invalid geometry bounds")
        solids, faces = len(row.shape.Solids()), len(row.shape.Faces())
        require(
            solids in (0, 1) and faces > 0, f"{path.name}: unexpected empty/multi-solid occurrence"
        )
        parts.append(
            {
                "index": row.index,
                "path": row.path,
                "name": row.name,
                "solids": solids,
                "faces": faces,
                "body_type": "solid" if solids else "sheet",
                "local_bounds_mm": local_bounds,
                "placement_mm": matrix.tolist(),
            }
        )
    require(sha256(path) == before, f"{path.name}: STEP changed while reading")
    require(
        len(parts) == 262 and sum(p["solids"] for p in parts) == 207,
        f"{path.name}: expected 262 occurrences / 207 solids / 55 sheets",
    )
    # doc/tool are held for the full traversal; only ordinary JSON is returned.
    del rows, doc, tool
    return {
        "filename": path.name,
        "sha256": before,
        "occurrences": len(parts),
        "solids": 207,
        "sheets": 55,
        "parts": parts,
    }


def by_name(parts):
    result = defaultdict(list)
    for part in parts:
        result[part["name"]].append(part)
    return {
        name: sorted(rows, key=lambda p: (p["solids"], p["local_bounds_mm"]))
        for name, rows in result.items()
    }


def group_members(parts, reference, groups):
    """Compare complete multisets, preserving repeated names within a group."""
    expected = Counter(
        (part["name"], part["body_type"]) for items in groups.values() for part in items
    )
    actual = Counter((part["name"], part["body_type"]) for part in parts)
    require(actual == expected, "Missing, extra or wrong-body-type group members")
    owner = {}
    for group, items in groups.items():
        for part in items:
            require(
                part["name"] not in owner or owner[part["name"]] == group,
                "Part name ambiguous across rigid groups; explicit occurrence IDs are needed",
            )
            owner[part["name"]] = group
    current, original = by_name(parts), by_name(reference)
    require(current.keys() == original.keys(), "Pose part names differ from frozen baseline")
    grouped, maximum = defaultdict(list), 0.0
    for name, rows in current.items():
        require(len(rows) == len(original[name]), f"{name}: occurrence multiplicity changed")
        for part, ref in zip(rows, original[name]):
            require(
                (part["solids"], part["faces"]) == (ref["solids"], ref["faces"]),
                f"{name}: source topology count changed",
            )
            delta = float(np.abs(np.array(part["local_bounds_mm"]) - ref["local_bounds_mm"]).max())
            maximum = max(maximum, delta)
            require(delta / 1000 < POSE_TOL, f"{name}: local bounds changed between poses")
            grouped[owner[name]].append(part)
    return grouped, maximum


def derive_case(target, data, reference, groups, joints):
    grouped, bbox_delta = group_members(data["parts"], reference, groups)
    instances, transforms = {}, {}
    for name, parts in grouped.items():
        require(len(parts) == len(groups[name]), f"{target['name']}/{name}: body count mismatch")
        matrices = np.array([part["placement_mm"] for part in parts])
        reference_matrix = matrices[0]
        relative_rotations = np.einsum("ji,njk->nik", reference_matrix[:3, :3], matrices[:, :3, :3])
        max_rotation = float(Rotation.from_matrix(relative_rotations).magnitude().max())
        max_translation_mm = float(
            np.linalg.norm(matrices[:, :3, 3] - reference_matrix[:3, 3], axis=1).max()
        )
        require(
            max_rotation < POSE_TOL and max_translation_mm / 1000 < POSE_TOL,
            f"{target['name']}/{name}: rigid members move differently "
            f"(rotation_rad={max_rotation}, translation_mm={max_translation_mm})",
        )
        transforms[name] = reference_matrix
        si = reference_matrix.copy()
        si[:3, 3] /= 1000
        instances[name] = {
            "transform_m": si.reshape(-1).tolist(),
            "body_count": len(parts),
            "max_member_rotation_element_delta": float(
                np.abs(matrices[:, :3, :3] - reference_matrix[:3, :3]).max()
            ),
            "max_member_translation_delta_mm": float(
                np.abs(matrices[:, :3, 3] - reference_matrix[:3, 3]).max()
            ),
            "max_member_rotation_rad": max_rotation,
            "max_member_translation_norm_mm": max_translation_mm,
        }
    observed, residuals = {}, {}
    require(
        {joint["name"] for joint in joints} == set(ACTIVE),
        "Expected five original native joint definitions",
    )
    for joint in joints:
        relative = np.linalg.inv(transforms[joint["a"]]) @ transforms[joint["b"]]
        basis = np.eye(3)["XYZ".index(joint["axis"])]
        axis = Rotation.from_rotvec(basis * np.radians(joint["rot"])).apply([0, 0, 1])
        observed[joint["name"]] = -float(
            np.degrees(Rotation.from_matrix(relative[:3, :3]).as_rotvec().dot(axis))
        )
        pivot = np.array(joint["xyz"])
        residuals[joint["name"]] = float(
            np.linalg.norm(relative[:3, 3] - (pivot - relative[:3, :3] @ pivot))
        )
    maximum_angle = max(abs(observed[key] - value) for key, value in target["expected_deg"].items())
    require(
        np.radians(maximum_angle) < POSE_TOL, f"{target['name']}: observed active angle differs"
    )
    require(max(residuals.values()) / 1000 < POSE_TOL, f"{target['name']}: joint pivot differs")
    return {
        "name": target["name"],
        "step_sha256": data["sha256"],
        "expected_deg": target["expected_deg"],
        "observed_from_step_deg": observed,
        "max_angle_error_deg": maximum_angle,
        "joint_pivot_translation_residual_mm": residuals,
        "max_local_bbox_delta_from_version_zero_mm": bbox_delta,
        "instances": instances,
    }


def replay(evidence, output, pose_dir=None):
    evidence, output = Path(evidence).resolve(), Path(output).resolve()
    pose_dir = Path(pose_dir).resolve() if pose_dir is not None else evidence / "CAD/native-poses"
    output.mkdir(parents=True, exist_ok=False)
    try:
        read_step, bounds, reader_file = assembly_reader()
        groups = load_json(evidence / "reports/expected-groups.json")["groups"]
        targets = load_json(evidence / "reports/native-pose-targets.json")["cases"]
        require(
            len(targets) == 11 and {case["name"] for case in targets} == set(CASE_NAMES),
            "Expected exactly the frozen eleven target cases",
        )
        joints = load_json(evidence / "robot/joint-definitions.json")[:5]
        baseline = inventory(evidence / "CAD/final-version.step", read_step, bounds)
        require(baseline["sha256"] == FINAL_STEP_SHA256, "Baseline is not the frozen V2 STEP")
        group_members(baseline["parts"], baseline["parts"], groups)
        for part in baseline["parts"]:
            require(
                np.allclose(part["placement_mm"], np.eye(4), atol=1e-9, rtol=0),
                "Frozen version must use neutral world-baked geometry",
            )
        write_json_exclusive(output / "baseline-inventory.json", baseline)
        cases = []
        for target in targets:
            data = inventory(pose_dir / f"{target['name']}.step", read_step, bounds)
            write_json_exclusive(output / f"native-step-{target['name']}.json", data)
            case = derive_case(target, data, baseline["parts"], groups, joints)
            cases.append(case)
            print(
                f"{target['name']}: {data['occurrences']} members; "
                f"angle_error_deg={case['max_angle_error_deg']:.9g}; local_bbox_delta_mm="
                f"{case['max_local_bbox_delta_from_version_zero_mm']:.9g}",
                flush=True,
            )
        runtime = {
            "python": sys.version.split()[0],
            **{
                name: importlib.metadata.version(name)
                for name in ("cadquery", "cadquery-ocp", "numpy", "scipy")
            },
        }
        report = {
            "method": "Fresh XCAF read of every archived STEP occurrence, not saved matrix JSON",
            "baseline_version": VERSION_ID,
            "baseline_step_sha256": baseline["sha256"],
            "length_unit": "m for transform_m; mm only for explicitly named diagnostics",
            "native_joint_sign": "negative child-relative rotation around the original mate connector Z",
            "verification_status": "RIGID_MEMBERS_PASS_FK_PENDING",
            "runtime": runtime,
            "reader_sha256": sha256(reader_file),
            "replay_script_sha256": sha256(Path(__file__)),
            "occurrences_per_pose": 262,
            "pose_occurrences_checked": 262 * len(cases),
            "total_occurrences_read_including_baseline": 262 * (len(cases) + 1),
            "max_member_rotation_element_delta": max(
                v["max_member_rotation_element_delta"]
                for c in cases
                for v in c["instances"].values()
            ),
            "max_member_translation_delta_mm": max(
                v["max_member_translation_delta_mm"] for c in cases for v in c["instances"].values()
            ),
            "cases": cases,
            "limitations": [
                "Independent installed CadQuery/OCP kernel, not the locked OCCT8 converter",
                "Archived UI exports only; no new live Onshape inspection",
                "Bounds/topology checks are not a proof of shape equivalence",
                "No strength, calibration, dynamics or fabrication approval",
            ],
        }
        write_json_exclusive(output / "native-pose-transforms.json", report)
        print(
            "PASS: all eleven STEP poses reread; run validate_robot.py --native on this report",
            flush=True,
        )
        return report
    except Exception as error:
        write_json_exclusive(
            output / "failure.json",
            {
                "status": "FAIL",
                "error_type": type(error).__name__,
                "error": str(error),
                "note": "Partial inventories are evidence of an incomplete/failed run, not a successful replay",
            },
        )
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=ROOT.parent)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New directory; never overwrites existing evidence",
    )
    parser.add_argument(
        "--pose-dir",
        type=Path,
        help="Alternative pose directory, e.g. the archived V1 negative control",
    )
    args = parser.parse_args(argv)
    try:
        replay(args.inputs, args.output, args.pose_dir)
        return 0
    except Exception as error:  # noqa: BLE001 -- CLI boundary reports a failed replay.
        print(
            json.dumps(
                {"status": "FAIL", "error_type": type(error).__name__, "error": str(error)},
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
