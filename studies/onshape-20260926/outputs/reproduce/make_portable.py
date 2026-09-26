"""Normalize this task's no_dynamics URDF, retaining the first raw export.

Usage: python3 make_portable.py outputs/new_robot_output
Do not apply to a robot with measured inertial properties.
"""

import argparse
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("directory", type=Path)
args = p.parse_args()
root = args.directory.resolve()
config = json.loads((root / "config.json").read_text())
if config.get("no_dynamics") is not True:
    raise SystemExit("This converter requires no_dynamics: true.")
src = root / "robot.urdf"
raw = root / "robot.onshape-raw.urdf"
if not raw.exists():
    shutil.copy2(src, raw)
tree = ET.parse(raw)
robot = tree.getroot()
if len(robot.findall("link")) != 16 or len(robot.findall("joint")) != 15:
    raise SystemExit("Expected this task's 16-link / 15-joint export.")
for link in robot.findall("link"):
    for tag in ("inertial", "origin"):
        for element in link.findall(tag):
            link.remove(element)
for joint in robot.findall("joint"):
    if joint.get("type") == "fixed":
        for tag in ("axis", "limit"):
            for element in joint.findall(tag):
                joint.remove(element)
for mesh in robot.findall(".//mesh"):
    filename = mesh.get("filename", "").removeprefix("package://")
    if not (root / filename).is_file():
        raise SystemExit(f"Missing mesh: {filename}")
    mesh.set("filename", filename)
ET.indent(tree, space="  ")
tree.write(src, encoding="utf-8", xml_declaration=True)
print("Portable kinematic URDF:", src)
print("Raw export retained:", raw)
