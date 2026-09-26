"""Measure round-trip surface distances when default mass integration differs."""

import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepTools import BRepTools
from OCP.TopLoc import TopLoc_Location

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "work/gripper-low-profile/scripts"))
from assembly_io import read_step

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/low-profile-250g"
files = [
    OUT / "CAD/Robot_250g_low_profile_D405.step",
    OUT / "CAD/native-poses/zero.step",
]
loaded = [read_step(p) for p in files]
parts = [{r.name: r.world for r in data[2]} for data in loaded]
names = [
    "ARM_P03_shoulder_XL430",
    "ARM_P02_yaw_carrier",
    "ARM_M04_ref08",
    "CAM5_BASE",
    "CAM5_D405_CARRIER",
    "PG3_finger_L",
    "PG3_finger_R",
]
results = []
for name in names:
    a, b = [p[name] for p in parts]
    meshes = []
    deflections = []
    for shape in [a, b]:
        BRepTools.Clean_s(shape.wrapped)
        mesher = BRepMesh_IncrementalMesh(shape.wrapped, 0.001, False, 0.1, True)
        assert mesher.IsDone()
        # Read the existing absolute mesh directly; CQ.mesh would remesh relatively.
        vertices = []
        faces = []
        face_deflections = []
        for face in shape.Faces():
            loc = TopLoc_Location()
            poly = BRep_Tool.Triangulation_s(face.wrapped, loc)
            assert poly is not None
            offset = len(vertices)
            for i in range(1, poly.NbNodes() + 1):
                p = poly.Node(i).Transformed(loc.Transformation())
                vertices.append((p.X(), p.Y(), p.Z()))
            faces.extend(
                tuple(t.Value(j) + offset - 1 for j in (1, 2, 3)) for t in poly.Triangles()
            )
            face_deflections.append(poly.Deflection())
        meshes.append(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))
        deflections.append(max(face_deflections))
    distances = []
    for source, target in [meshes, meshes[::-1]]:
        samples = np.concatenate([source.vertices, source.triangles_center])
        chunks = []
        for batch in np.array_split(samples, max(1, int(np.ceil(len(samples) / 1000)))):
            chunks.append(trimesh.proximity.closest_point(target, batch)[1])
        distances.append(np.concatenate(chunks))
    result = {
        "name": name,
        "source_volume_default_mm3": a.Volume(),
        "native_volume_default_mm3": b.Volume(),
        "source_volume_adaptive_1e10_mm3": a.Volume(1e-10),
        "native_volume_adaptive_1e10_mm3": b.Volume(1e-10),
        "sample_counts": [len(d) for d in distances],
        "max_reported_mesh_deflection_mm": deflections,
        "max_bidir_sample_distance_mm": max(float(d.max()) for d in distances),
        "p99_bidir_sample_distance_mm": max(float(np.quantile(d, 0.99)) for d in distances),
    }
    results.append(result)
    print(result, flush=True)
report = {
    "method": "Bidirectional vertices and triangle centers to opposite mesh after absolute OCCT tessellation; raw distances, no new acceptance threshold.",
    "tessellation_linear_mm": 0.001,
    "tessellation_angular_rad": 0.1,
    "scope": "Seven selected components only; discrete surface comparison, not a complete Hausdorff or material symmetric-difference proof.",
    "parts": results,
}
(OUT / "reports/native-step-geometry-diagnostic.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
