"""Prepare explicit SI link/joint settings from the recorded Onshape design."""

import json
import math
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/low-profile-250g"


def frame(xyz):
    transform = np.eye(4)
    transform[:3, 3] = np.asarray(xyz) / 1000
    return transform.tolist()


def main():
    groups = json.loads((OUT / "reports/expected-groups.json").read_text())["groups"]
    definitions = json.loads((OUT / "robot/joint-definitions.json").read_text())
    config = {
        "schema_version": 1,
        "robot_name": "low_cost_robot_d405_low_profile",
        "root": "base_link",
        "length_unit": "m",
        "linear_deflection_mm": 0.1,
        "angular_deflection_rad": 0.1,
        "limitations": "Kinematic study: effort/velocity zero are unset placeholders, no dynamics ratings or inertials.",
        "links": {},
        "joints": [],
        "loop_constraints": [],
    }
    for name, members in groups.items():
        config["links"][name] = {
            "frame_m": frame([0, 0, 0]),
            "parts": sorted({member["name"] for member in members}),
            "expected_occurrences": len(members),
        }
    for definition in definitions:
        name = definition["name"]
        if definition.get("closing"):
            ends = []
            for number, parent in enumerate((definition["a"], definition["b"]), 1):
                child = f"{name}_{number}"
                ends.append(child)
                config["links"][child] = {
                    "frame_m": frame(definition["xyz"]),
                    "parts": [],
                    "expected_occurrences": 0,
                }
                config["joints"].append(
                    {
                        "name": f"{child}_fixed",
                        "parent": parent,
                        "child": child,
                        "type": "fixed",
                    }
                )
            config["loop_constraints"].append(
                {
                    "name": name,
                    "type": "coincident_points",
                    "links": ends,
                    "coupling": "pg3_states.py",
                }
            )
            continue
        kind = {"REVOLUTE": "revolute", "SLIDER": "prismatic", "FASTENED": "fixed"}[
            definition["type"]
        ]
        config["links"][definition["b"]]["frame_m"] = frame(definition["xyz"])
        joint = {
            "name": name,
            "parent": definition["a"],
            "child": definition["b"],
            "type": kind,
        }
        if kind != "fixed":
            # Positive native mate values move the child around negative connector Z.
            axis = -Rotation.from_euler(
                definition["axis"].lower(), definition["rot"], degrees=True
            ).apply([0, 0, 1])
            joint["axis"] = axis.tolist()
            limits = definition.get("limits", [-180, 180])
            scale = math.pi / 180 if kind == "revolute" else 0.001
            joint["limit"] = {
                "lower": limits[0] * scale,
                "upper": limits[1] * scale,
                "effort": 0,
                "velocity": 0,
            }
        config["joints"].append(joint)
    path = OUT / "robot/converter-config.json"
    path.write_text(json.dumps(config, indent=2) + "\n")
    print(path)


if __name__ == "__main__":
    main()
