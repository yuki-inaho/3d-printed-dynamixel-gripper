"""Extract rigid-group transforms and observed joint angles from UI STEP files."""

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/low-profile-250g"
targets = json.loads((OUT / "reports/native-pose-targets.json").read_text())["cases"]
groups = json.loads((OUT / "reports/expected-groups.json").read_text())["groups"]
joints = json.loads((OUT / "robot/joint-definitions.json").read_text())[:5]
name_to_group = {p["name"]: group for group, parts in groups.items() for p in parts}
zero = json.loads((OUT / "reports/native-step-zero.json").read_text())


def by_name(parts):
    result = defaultdict(list)
    for p in parts:
        result[p["name"]].append(p)
    return {
        name: sorted(rows, key=lambda x: (x["solids"], x["local_bounds_mm"]))
        for name, rows in result.items()
    }


zero_by_name = by_name(zero["parts"])
results = []
for target in targets:
    name = target["name"]
    data = json.loads((OUT / "reports" / f"native-step-{name}.json").read_text())
    actual = by_name(data["parts"])
    assert actual.keys() == zero_by_name.keys()
    local_bbox_deltas = []
    per_group = defaultdict(list)
    for part_name, rows in actual.items():
        assert len(rows) == len(zero_by_name[part_name])
        for p, ref in zip(rows, zero_by_name[part_name]):
            assert p["solids"] == ref["solids"]
            local_bbox_deltas.append(
                float(np.abs(np.array(p["local_bounds_mm"]) - ref["local_bounds_mm"]).max())
            )
            per_group[name_to_group[part_name]].append(p)
    transforms = {}
    instances = {}
    for group, parts in per_group.items():
        assert len(parts) == len(groups[group])
        matrices = np.array([p["placement_mm"] for p in parts])
        ref = matrices[0]
        transforms[group] = ref
        si = ref.copy()
        si[:3, 3] /= 1000
        instances[group] = {
            "transform_m": si.reshape(-1).tolist(),
            "body_count": len(parts),
            "max_member_rotation_element_delta": float(
                np.abs(matrices[:, :3, :3] - ref[:3, :3]).max()
            ),
            "max_member_translation_delta_mm": float(np.abs(matrices[:, :3, 3] - ref[:3, 3]).max()),
        }
    observed = {}
    residuals = {}
    for joint in joints:
        relative = np.linalg.inv(transforms[joint["a"]]) @ transforms[joint["b"]]
        basis = np.eye(3)["XYZ".index(joint["axis"])]
        axis = Rotation.from_rotvec(basis * np.radians(joint["rot"])).apply([0, 0, 1])
        angle = -float(np.degrees(Rotation.from_matrix(relative[:3, :3]).as_rotvec().dot(axis)))
        observed[joint["name"]] = angle
        pivot = np.array(joint["xyz"])
        residuals[joint["name"]] = float(
            np.linalg.norm(relative[:3, 3] - (pivot - relative[:3, :3] @ pivot))
        )
    results.append(
        {
            "name": name,
            "step_sha256": data["sha256"],
            "expected_deg": target["expected_deg"],
            "observed_from_step_deg": observed,
            "max_angle_error_deg": max(
                abs(observed[n] - v) for n, v in target["expected_deg"].items()
            ),
            "joint_pivot_translation_residual_mm": residuals,
            "max_local_bbox_delta_from_version_zero_mm": max(local_bbox_deltas),
            "instances": instances,
        }
    )
    print(
        name,
        "angle max deg",
        results[-1]["max_angle_error_deg"],
        "local bbox delta mm",
        max(local_bbox_deltas),
        flush=True,
    )
max_rotation_delta = max(
    v["max_member_rotation_element_delta"] for c in results for v in c["instances"].values()
)
max_translation_delta = max(
    v["max_member_translation_delta_mm"] for c in results for v in c["instances"].values()
)
rigid_members_match = max_rotation_delta <= 2e-5 and max_translation_delta / 1000 <= 2e-5
report = {
    "method": "XCAF occurrence placements from actual UI STEP exports, grouped by declared unique part-name membership",
    "baseline_version": json.loads((OUT / "project.json").read_text())["version_id"],
    "length_unit": "m for transform_m; mm only for explicit diagnostic fields",
    "native_joint_sign": "negative of child relative rotation around original mate connector Z, derived from positive native yaw pilot",
    "verification_status": "RIGID_MEMBERS_PASS_FK_PENDING"
    if rigid_members_match
    else "FAIL_RIGID_MEMBER_MOTION",
    "max_member_rotation_element_delta": max_rotation_delta,
    "max_member_translation_delta_mm": max_translation_delta,
    "cases": results,
}
(OUT / "reports/native-pose-transforms.json").write_text(json.dumps(report, indent=2) + "\n")
print(
    "EXTRACTED",
    len(results),
    "poses and",
    sum(len(c["instances"]) for c in results),
    "rigid transforms",
    flush=True,
)
if not rigid_members_match:
    raise SystemExit("FAIL: components assigned to one rigid group do not move together")
