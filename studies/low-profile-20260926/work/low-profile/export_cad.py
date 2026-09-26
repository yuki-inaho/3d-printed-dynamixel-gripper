"""Export, reload, and compare actual low-profile candidate CAD."""

import hashlib
import json

import cadquery as cq
import numpy as np
import trimesh
from compare import candidate_spec
from design import extended_arm, load_source, preservation
from paths import COMPACT_STEP
from study import OUT, save

from gripper_design import camera_overhead_d405_r5 as r5
from gripper_design.camera_overhead_r4 import ANCHORS
from scripts.assembly_io import bounds, read_step
from scripts.build_camera_overhead_d405_r5 import color
from scripts.render_cad import render


def main():
    row = json.loads((OUT / "reports/selection.json").read_text())
    spec = candidate_spec(row)
    source = load_source()
    arm = extended_arm(source, row["extension_mm"])
    mount = r5.build(spec)
    parts = arm | mount
    folder = OUT / "CAD"
    folder.mkdir(exist_ok=True)
    path = folder / "Robot_250g_low_profile_D405.step"
    assembly = cq.Assembly(name="Robot_250g_low_profile_D405")
    for name, shape in parts.items():
        assembly.add(shape, name=name, color=cq.Color(*color(name)))
    assembly.save(str(path))
    print("saved assembly", flush=True)
    new = {r.name: r.world for r in read_step(path)[2]}
    if set(new) != set(parts):
        raise AssertionError("Occurrence identity mismatch on STEP roundtrip")
    checks = []
    for name, shape in parts.items():
        other = new[name]
        err = {
            "name": name,
            "volume_mm3": abs(shape.Volume() - other.Volume()),
            "area_mm2": abs(shape.Area() - other.Area()),
            "bounds_mm": float(np.abs(np.array(bounds(shape)) - bounds(other)).max()),
            "same_solid_count": len(shape.Solids()) == len(other.Solids()),
        }
        err["pass"] = (
            err["volume_mm3"] < 0.01
            and err["area_mm2"] < 0.01
            and err["bounds_mm"] < 1e-4
            and err["same_solid_count"]
        )
        checks.append(err)
    changed = {"PG3_finger_L", "PG3_finger_R", "PG3_pad_L", "PG3_pad_R"}
    retained = [n for n in source if n not in changed]
    assert all(parts[n] is source[n] for n in retained)
    mask_checks = {
        side: preservation(
            source[f"PG3_finger_{side}"], new[f"PG3_finger_{side}"], row["extension_mm"]
        )
        for side in ["L", "R"]
    }
    printed = ["CAM5_BASE", "CAM5_D405_CARRIER", "PG3_finger_L", "PG3_finger_R"]
    stl_checks = {}
    for name in printed:
        shape = new[name]
        cq.exporters.export(shape, str(folder / f"{name}.step"))
        stl = folder / f"{name}.stl"
        cq.exporters.export(shape, str(stl), tolerance=0.05, angularTolerance=0.1)
        mesh = trimesh.load(stl)
        stl_checks[name] = {
            "brep_valid": shape.isValid(),
            "solid_count": len(shape.Solids()),
            "volume_mm3": shape.Volume(),
            "watertight": bool(mesh.is_watertight),
            "mesh_components": len(mesh.split()),
            "stl_sha256": hashlib.sha256(stl.read_bytes()).hexdigest(),
        }
    probes = []
    for x, y, z in ANCHORS:
        probe = cq.Solid.makeCylinder(1.3, 2, cq.Vector(x, y, z + 0.05))
        probes.append(abs(new["CAM5_BASE"].intersect(probe).Volume()))
    report = {
        "cad_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "occurrences": len(new),
        "bodies": sum(
            len(s.Solids()) if s.Solids() else len(s.Shells()) or len(s.Faces())
            for s in new.values()
        ),
        "preserved_occurrences": retained,
        "preserved_count": len(retained),
        "source_object_identity_preserved": True,
        "roundtrip_checks": checks,
        "root_mask_checks": mask_checks,
        "printed_parts": stl_checks,
        "anchor_probe_overlap_mm3": probes,
        "d405_screw_stack": r5.d405_stack(spec),
        "existing_urdf_matches_candidate": False,
        "roundtrip_signature_is_full_arbitrary_shape_equivalence_proof": False,
    }
    report["pass"] = (
        all(r["pass"] for r in checks)
        and all(v["pass"] for v in mask_checks.values())
        and max(probes) < 1e-5
        and all(
            v["brep_valid"]
            and v["solid_count"] == 1
            and v["watertight"]
            and v["mesh_components"] == 1
            for v in stl_checks.values()
        )
    )
    save("cad-export.json", report)
    if not report["pass"]:
        raise AssertionError("Saved CAD contract failed; inspect cad-export.json")
    compact = {r.name: r.world for r in read_step(COMPACT_STEP)[2]}
    for label, scene in [("compact75", compact), ("low_profile30", new)]:
        render(
            [(s, color(n)) for n, s in scene.items()],
            OUT / "images" / f"{label}_side.png",
            direction=(1, 0, 0),
            focus=(-0.2, 175, 213),
            scale=90,
            size=(1100, 900),
        )
        render(
            [(s, color(n)) for n, s in scene.items()],
            OUT / "images" / f"{label}_assembly.png",
            direction=(1, -0.6, 0.5),
            focus=(-0.2, 140, 170),
            scale=165,
            size=(1200, 1000),
        )
    print("EXPORT PASS", report["cad_sha256"], len(new), len(retained), flush=True)


if __name__ == "__main__":
    main()
