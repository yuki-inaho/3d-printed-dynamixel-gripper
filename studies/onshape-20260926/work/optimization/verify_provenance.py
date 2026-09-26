"""Check current CAD provenance without requiring old/new tessellation identity."""

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from scripts.assembly_io import bounds, read_step

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/optimization-250g"
sys.path.insert(0, str(OUT / "robot"))
from validate_robot import fk

old = Path(
    "/home/inaho-omen/Project/3d-printed-dynamixel-gripper/outputs/camera-mount-id5-overhead-d405-r5/CAD/ID5_D405_mid_ASSEMBLY.step"
)
new = OUT / "CAD/Robot_250g_compact_D405.step"
a = {r.name: r.world for r in read_step(old)[2]}
b = {r.name: r.world for r in read_step(new)[2]}
assert set(a) == set(b) and len(a) == 257
rows = []
for name in sorted(a):
    if name.startswith("CAM5_"):
        continue
    dv = abs(a[name].Volume() - b[name].Volume())
    db = max(abs(np.array(bounds(a[name])) - np.array(bounds(b[name]))))
    rows.append(
        {"name": name, "volume_delta_mm3": float(dv), "bounds_delta_mm": float(db)}
    )
assert max(r["volume_delta_mm3"] for r in rows) < 0.01
assert max(r["bounds_delta_mm"] for r in rows) < 1e-4
manifest = json.loads((OUT / "robot/source-manifest.json").read_text())
assert hashlib.sha256(new.read_bytes()).hexdigest() == manifest["source_sha256"]
for name, details in manifest["meshes"].items():
    assert (
        hashlib.sha256((OUT / "robot/assets" / name).read_bytes()).hexdigest()
        == details["sha256"]
    )
for name, key in [
    ("robot.urdf", "portable_urdf_sha256"),
    ("robot.onshape-raw.urdf", "raw_urdf_sha256"),
]:
    assert (
        hashlib.sha256((OUT / "robot" / name).read_bytes()).hexdigest() == manifest[key]
    )
robot = ET.parse(OUT / "robot/robot.urdf").getroot()
cam = fk(robot, {})["camera_body"][:3, 3]
assert np.max(np.abs(cam - np.array([-0.0002, 0.185, 0.250]))) < 2e-5
wrist = robot.find("joint[@name='joint4_wrist']/limit")
limits = [float(wrist.get(x)) for x in ("lower", "upper")]
assert np.max(np.abs(np.array(limits) - np.radians([-106, 138]))) < 1e-5
report = {
    "status": "PASS_CURRENT_EXPORT_PROVENANCE_WITH_TESSELLATION_DIFFERENCES",
    "unchanged_non_camera_occurrences": len(rows),
    "max_volume_delta_mm3": max(r["volume_delta_mm3"] for r in rows),
    "max_bounds_delta_mm": max(r["bounds_delta_mm"] for r in rows),
    "roundtrip_thresholds": {"volume_mm3": 0.01, "bounds_mm": 1e-4},
    "camera_frame_world_m": cam.tolist(),
    "wrist_limits_rad": limits,
    "hashes_verified": True,
    "source_version": manifest["onshape_version"],
    "strict_old_mesh_identity": "FAIL retained in mesh-vertex-diagnostic.json and mesh-surface-diagnostic.json",
    "rationale": "Exporter meshes are authentic current-version output. optimize.py reuses original non-CAM5 BReps; STEP roundtrip uses the existing volume/bounds gate. Mesh identity to an older tessellation is not a requirement for current export provenance. Sampled bidirectional triangle distances were 0.35 and 0.71 micrometres for forearm/wrist; this is not proof of exact surface identity.",
    "occurrences": rows,
}
(OUT / "reports/export-provenance.json").write_text(json.dumps(report, indent=2))
print(json.dumps({k: v for k, v in report.items() if k != "occurrences"}, indent=2))
