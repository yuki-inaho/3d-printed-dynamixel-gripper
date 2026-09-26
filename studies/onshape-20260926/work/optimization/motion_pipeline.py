"""Complete the compact candidate's native assembly; never modify the source repos."""

import argparse
import copy
import json
import math
import os
import runpy
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "work/optimization/motion"
OUT = ROOT / "outputs/optimization-250g"
STATIC = ROOT / "work/optimization/onshape"
NAME = "Compact D405 - Motion and URDF"
STATE.mkdir(parents=True, exist_ok=True)
os.environ["ONSHAPE_TASK_WORK"] = str(STATE)
os.environ["ONSHAPE_TASK_OUTPUT"] = str(OUT)
sys.path.insert(0, str(ROOT / "work"))
import onshape_api as client
from joint_definitions import JOINTS as ORIGINAL_JOINTS

api = client.api


def write(name, data):
    (STATE / name).write_text(json.dumps(data, indent=2) + "\n")


def bind():
    project = json.loads((STATE / "project.json").read_text())
    assert project["did"] == "7b85d8922959cbe564b6e0cb"
    client.DID, client.WID, client.PS, client.ASM = (
        project[k] for k in ("did", "wid", "ps", "asm")
    )
    return project


def assembly(project):
    return api(
        f"/assemblies/d/{project['did']}/w/{project['wid']}/e/{project['asm']}",
        query={
            "includeMateConnectors": "true",
            "includeMateFeatures": "true",
            "includeNonSolids": "true",
        },
    )


def setup():
    project = json.loads((STATIC / "project.json").read_text())
    did, wid, ps = (project[k] for k in ("did", "wid", "ps"))
    assert did == "7b85d8922959cbe564b6e0cb"
    if not (STATE / "project.json").exists():
        elements = api(f"/documents/d/{did}/w/{wid}/elements")
        matches = [e for e in elements if e.get("name") == NAME]
        assert len(matches) <= 1, "Ambiguous assembly name; inspect before retry"
        created = (
            matches[0]
            if matches
            else api(f"/assemblies/d/{did}/w/{wid}", "POST", {"name": NAME})
        )
        project["asm"] = created["id"]
        write("project.json", project)
    project = bind()
    parts = api(f"/parts/d/{did}/w/{wid}/e/{ps}")
    write("composite-parts.json", parts)
    shutil.copy2(STATIC / "composites.json", STATE / "composites.json")
    for filename in ("ps-specs.json", "asm-specs.json"):
        shutil.copy2(ROOT / "work" / filename, STATE / filename)
    names = list(json.loads((STATE / "composites.json").read_text()))
    composites = [p for p in parts if p["bodyType"] == "composite"]
    assert len(composites) == len(names) == 12
    # Existing builder pairs this list with the names, so enforce the same order.
    by_name = {p["name"]: p for p in composites}
    assert set(by_name) == set(names)
    write("composite-parts.json", [by_name[n] for n in names])
    existing = {
        i["name"].split(" <")[0]: i["id"]
        for i in assembly(project)["rootAssembly"]["instances"]
    }
    for name in names:
        if name in existing:
            continue
        api(
            f"/assemblies/d/{did}/w/{wid}/e/{project['asm']}/instances",
            "POST",
            {
                "documentId": did,
                "elementId": ps,
                "partId": by_name[name]["partId"],
                "isAssembly": False,
                "isFixed": name == "base_link",
            },
        )
        print("Inserted", name, flush=True)
    result = assembly(project)
    write("assembly-initial.json", result)
    assert len(result["rootAssembly"]["instances"]) == 12
    joints = copy.deepcopy(ORIGINAL_JOINTS)
    for joint in joints:
        if joint["name"] == "joint4_wrist":
            joint["limits"] = [-106, 138]
        if joint["name"] == "camera_body_fixed":
            joint["xyz"] = [-0.2, 185, 250]
    write("joint-definitions.json", joints)
    print("Prepared", project, flush=True)


def build():
    bind()
    # Reuse the proven API construction without changing the old definitions.
    import joint_definitions

    joint_definitions.JOINTS = json.loads(
        (STATE / "joint-definitions.json").read_text()
    )
    runpy.run_path(str(ROOT / "work/build_joints.py"), run_name="__main__")


def test_motion():
    project = bind()
    mates = json.loads((STATE / "mates.json").read_text())
    active = [
        "joint1_yaw",
        "joint2_shoulder",
        "joint3_elbow",
        "joint4_wrist",
        "gripper_drive",
    ]
    cases = [("zero", {})] + [("small_" + name, {name: 10}) for name in active]
    cases += [
        ("wrist_lower", {"joint4_wrist": -106}),
        ("wrist_upper", {"joint4_wrist": 138}),
        ("gripper_open", {"gripper_drive": 65}),
        ("gripper_closed", {"gripper_drive": -45}),
        ("restored_mid", {}),
    ]
    path = f"/assemblies/d/{project['did']}/w/{project['wid']}/e/{project['asm']}"
    report = {"project": project, "cases": [], "status": "RUNNING"}
    report_path = OUT / "reports/native-motion.json"
    current = {name: 0.0 for name in active}
    transitions = []

    def route(target, label):
        nonlocal current
        begin = current.copy()
        steps = max(
            1,
            math.ceil(
                max(abs(target[n] - begin[n]) for n in active) / math.radians(10)
            ),
        )
        for step in range(1, steps + 1):
            waypoint = {
                n: begin[n] + (target[n] - begin[n]) * step / steps for n in active
            }
            values = [
                {
                    "jsonType": "Revolute",
                    "featureId": mates["dof_" + name]["feature"]["featureId"],
                    "rotationZ": angle,
                    "ownerOccurrencePath": [],
                }
                for name, angle in waypoint.items()
            ]
            response = api(path + "/matevalues", "POST", {"mateValues": values})
            by_name = {v["mateName"]: v for v in response["mateValues"]}
            current = {n: by_name["dof_" + n]["rotationZ"] for n in active}
            error = max(abs(current[n] - waypoint[n]) for n in active)
            transitions.append(
                {
                    "target": label,
                    "step": step,
                    "steps": steps,
                    "expected_rad": waypoint,
                    "achieved_rad": current.copy(),
                    "max_error_rad": error,
                }
            )
            write("motion-transitions.json", transitions)
            assert error < 2e-5, transitions[-1]
        return response

    for label, changes in cases:
        route({name: 0.0 for name in active}, "reset_before_" + label)
        expected = {name: math.radians(changes.get(name, 0)) for name in active}
        achieved = route(expected, label)
        write(f"pose-{label}-matevalues.json", achieved)
        pose = assembly(project)
        write(f"pose-{label}.json", pose)
        by_name = {v["mateName"]: v for v in achieved["mateValues"]}
        error = max(
            abs(by_name["dof_" + name]["rotationZ"] - angle)
            for name, angle in expected.items()
        )
        displacement = max(
            float(np.max(np.abs(np.array(o["transform"]).reshape(4, 4) - np.eye(4))))
            for o in pose["rootAssembly"]["occurrences"]
        )
        row = {
            "case": label,
            "expected_rad": expected,
            "achieved_rad": {
                name: by_name["dof_" + name]["rotationZ"] for name in active
            },
            "max_requested_value_error_rad": error,
            "max_occurrence_matrix_change": displacement,
        }
        report["cases"].append(row)
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        assert error < 2e-5, row
        if changes:
            assert displacement > 1e-6, "Mate values changed but geometry did not"
        else:
            assert displacement < 2e-5, row
        print(
            label,
            "requested/achieved error",
            error,
            "matrix delta",
            displacement,
            flush=True,
        )
    report["status"] = "PASS_NATIVE_SAMPLED_MOTION"
    report["continuous_collision_proof"] = False
    report["method"] = (
        "Reset to zero before each case; waypoints <=10deg; verify every achieved value"
    )
    report["transition_count"] = len(transitions)
    report["max_transition_error_rad"] = max(t["max_error_rad"] for t in transitions)
    report_path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["setup", "build", "test-motion"])
    args = parser.parse_args()
    {"setup": setup, "build": build, "test-motion": test_motion}[args.stage]()
