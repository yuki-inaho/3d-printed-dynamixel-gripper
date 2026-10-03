"""Replace only P05 in the frozen V2 XCAF, export and review a local candidate."""

import argparse
import hashlib
import importlib.metadata
import json
from dataclasses import asdict
from itertools import combinations
from pathlib import Path

import cadquery as cq
import trimesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.StepRepr import StepRepr_NextAssemblyUsageOccurrence
from OCP.TCollection import TCollection_ExtendedString, TCollection_HAsciiString
from OCP.TDataStd import TDataStd_Name

from gripper_design.p05_cable_clearance import (
    DEFAULT_SOURCE,
    DEFAULT_WINDOW,
    SOURCE_SHA256,
    candidate,
    change_mask,
    nominal_plug_corridors,
    seat_preservation,
    volume,
)
from gripper_design.p05_cable_relief import diagnostic_wires, protected
from gripper_design.pg3 import shape_signature_difference
from scripts.assembly_io import bounds, read_step
from scripts.probe_pg3_wire_routes import terminal_centres
from scripts.review_pg3 import inspect_pairs

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def control(shape):
    record = {
        "valid": shape.isValid(),
        "self_cut_mm3": volume(shape.cut(shape.copy())),
        "self_common_mm3": volume(shape.intersect(shape.copy())),
        "own_volume_mm3": volume(shape),
    }
    record["passed"] = (
        record["valid"]
        and record["self_cut_mm3"] < 1e-4
        and abs(record["self_common_mm3"] - record["own_volume_mm3"]) < 1e-4
    )
    if not record["passed"]:
        raise ValueError("P05 Boolean control failed")
    return record


def verify_occurrences(before, after):
    identities = lambda rs: [(r.index, r.path, r.name) for r in rs]
    if identities(before) != identities(after):
        raise ValueError("saved occurrence identities changed")
    # Serialization changes ~1e-28 roundoff in near-zero rotations. Compare the
    # actual placement matrices at 1e-12, tighter than geometry's existing 1e-5.
    delta = max(
        abs(a.loc.wrapped.Transformation().Value(i, j) - b.loc.wrapped.Transformation().Value(i, j))
        for a, b in zip(before, after)
        for i in range(1, 4)
        for j in range(1, 5)
    )
    if delta > 1e-12:
        raise ValueError("saved occurrence placements changed")
    return {"identities_equal": True, "max_placement_matrix_delta": delta}


def name_replacement_product(writer, owner):
    """Retain the product name used by Chili3D as well as the XCAF owner name."""
    model = writer.ChangeWriter().Model()
    products = []
    for i in range(1, model.NbEntities() + 1):
        entity = model.Value(i)
        if (
            isinstance(entity, StepRepr_NextAssemblyUsageOccurrence)
            and entity.Name().ToCString() == owner
        ):
            products.append(entity.RelatedProductDefinition().Formation().OfProduct())
    if len(products) != 1:
        raise ValueError("replacement product ownership is ambiguous")
    products[0].SetName(TCollection_HAsciiString(owner))


def run(source, out, spec=DEFAULT_WINDOW):
    if sha(source) != SOURCE_SHA256:
        raise ValueError("source SHA differs from frozen Onshape V2")
    doc, shape_tool, rows = read_step(source)
    p05_rows = [r for r in rows if r.name == "ARM_P05_wrist_XL430"]
    cases = [r.world for r in rows if r.name == "PG3_XL430_fixed"]
    if len(rows) != 262 or len(p05_rows) != 1 or len(cases) != 2:
        raise ValueError("unexpected saved V2 occurrence inventory")
    occurrence = p05_rows[0]
    old = occurrence.world
    new = candidate(old, cases, spec)
    controls = {"source": control(old), "candidate": control(new)}
    out.mkdir(parents=True, exist_ok=False)
    step = out / "P05_CABLE_CLEARANCE_CANDIDATE.step"
    stl = out / "P05_CABLE_CLEARANCE_CANDIDATE.stl"
    assembly = out / "V2_P05_CABLE_CLEARANCE_CANDIDATE.step"
    cq.exporters.export(new, str(step))
    cq.exporters.export(new, str(stl), tolerance=0.12, angularTolerance=0.18)

    # Replace one definition in its local frame. Preserve the supplied hierarchy,
    # occurrence placements, colours and duplicate-name motor leaves.
    shape_tool.SetShape(occurrence.label, new.moved(occurrence.loc.inverse).wrapped)
    # SetShape regenerates the definition's automatic name; retain its owner.
    TDataStd_Name.Set_s(occurrence.label, TCollection_ExtendedString(occurrence.name))
    shape_tool.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    writer.SetColorMode(True)
    if not writer.Transfer(doc, STEPControl_AsIs):
        raise ValueError("XCAF transfer failed")
    name_replacement_product(writer, occurrence.name)
    if writer.Write(str(assembly)) != IFSelect_RetDone:
        raise ValueError("assembly STEP export failed")
    saved_rows = read_step(assembly)[2]
    occurrence_check = verify_occurrences(rows, saved_rows)
    saved_p05 = saved_rows[occurrence.index].world
    controls["saved_assembly_P05"] = control(saved_p05)
    standalone = cq.importers.importStep(str(step)).val()
    controls["saved_standalone_P05"] = control(standalone)
    for shape in (saved_p05, standalone):
        if volume(shape.cut(new)) + volume(new.cut(shape)) > 1e-4:
            raise ValueError("saved P05 differs from candidate")
    signatures = {
        f"{old_row.index:03d}:{old_row.name}": shape_signature_difference(
            old_row.world, new_row.world
        )
        for old_row, new_row in zip(rows, saved_rows)
        if old_row.index != occurrence.index
    }
    if any(
        s["vertex_distance_mm"] > 1e-5
        or s["volume_error_mm3"] > 1e-3
        or not s["vertex_count_equal"]
        or not s["face_count_equal"]
        for s in signatures.values()
    ):
        raise ValueError("unmodified occurrence roundtrip signature differs")
    (out / "unchanged-occurrences.json").write_text(json.dumps(signatures, indent=2) + "\n")
    print("Saved all 262 identities and placements; 261 unchanged signatures pass.", flush=True)

    shapes = {f"{r.index:03d}:{r.name}": r.world for r in saved_rows}
    p05_key = f"{occurrence.index:03d}:{occurrence.name}"
    wires = diagnostic_wires()
    for port in (3, 4):
        before = next(r.world for r in rows if r.name == f"ARM_M05_ref{port:02d}")
        after = next(r.world for r in saved_rows if r.name == f"ARM_M05_ref{port:02d}")
        old_points, old_pcb = terminal_centres(before)
        points, pcb = terminal_centres(after)
        if abs(old_pcb - pcb) > 1e-6 or any(
            abs(a - b) > 1e-6 for p, q in zip(old_points, points) for a, b in zip(p, q)
        ):
            raise ValueError("diagnostic wire terminal frame changed")
    pairs = [(p05_key, k) for k in shapes if k != p05_key]
    pairs += [(w, k) for w in wires for k in shapes]
    pairs += list(combinations(wires, 2))
    contacts = inspect_pairs(shapes | wires, pairs)
    (out / "contacts.json").write_text(json.dumps(contacts, indent=2) + "\n")

    plugs = nominal_plug_corridors(spec)
    plug_window = inspect_pairs(
        {"old_P05": old, "new_P05": saved_p05} | plugs,
        [(p, n) for p in plugs for n in ("old_P05", "new_P05")],
    )
    plug_installed = inspect_pairs(shapes | plugs, [(p, k) for p in plugs for k in shapes])
    (out / "plug-with-motor-diagnostic.json").write_text(
        json.dumps(plug_installed, indent=2) + "\n"
    )
    removed = old.cut(saved_p05)
    mesh = trimesh.load(str(stl), force="mesh")
    mesh_checks = {
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "components": len(mesh.split(only_watertight=False)),
        "volume_positive": bool(mesh.volume > 0),
        "linear_tessellation_mm": 0.12,
        "angular_tessellation": 0.18,
    }
    if not all(mesh_checks[k] for k in ("watertight", "winding_consistent", "volume_positive")):
        raise ValueError("bad STL topology")
    if mesh_checks["components"] != 1:
        raise ValueError("disconnected STL")
    report = {
        "source": str(source.relative_to(ROOT)),
        "source_sha256": sha(source),
        "source_onshape_version": "f6162b4adc88af9d07f1194a",
        "source_onshape_url": "https://cad.onshape.com/documents/29e8557c76e89bcf64f50566/v/f6162b4adc88af9d07f1194a/e/d5415bf725ba822741b01703",
        "operation": "replace only P05 geometry in copied XCAF; original V2 unchanged",
        "replacement_product_name": occurrence.name,
        "units": "mm",
        "window_spec": asdict(spec),
        "source_window_mm": [3, 8],
        "occurrences": len(saved_rows),
        "unchanged_signature_count": len(signatures),
        "excluded_occurrences": [],
        "occurrence_check": occurrence_check,
        "P05_bounds_mm": bounds(saved_p05),
        "removed_volume_mm3": volume(removed),
        "outside_mask_loss_mm3": volume(removed.cut(change_mask(spec))),
        "protected_loss_mm3": volume(removed.intersect(protected())),
        "case_seats": seat_preservation(old, saved_p05, cases),
        "boolean_controls": controls,
        "mesh_checks": mesh_checks,
        "contacts_counts": contacts["counts"],
        "contacts_nonpass": [r for r in contacts["pairs"] if r["status"] != "PASS"],
        "wire_sidewall_clearance_mm": min(saved_p05.distance(w) for w in wires.values()),
        "wire_cover_clearance_mm": min(
            r["distance_mm"]
            for r in contacts["pairs"]
            if r["a"] in wires and r["b"].endswith(":ARM_M05_ref06")
        ),
        "plug_window_only_before_motor_installation": plug_window,
        "plug_straight_access_with_motor_installed_counts": plug_installed["counts"],
        "limits": [
            "OD1.9 mm, bend centreline R1.2 mm and PCB-to-wire-exit8.7 mm are assumptions",
            "Internal 90-degree bend followed by straight sideways exit; not straight rear exit",
            "EHR-3 nominal housing9.5x3.8 is a window passage diagnostic before motor insertion",
            "The saved-motor plug corridor remains a separate diagnostic, not an accepted installation path",
            "Printed fit, bend allowance, strain relief, prewired motor insertion, fastening and strength unknown",
            "Unchanged signatures are not full material-set Boolean equivalence for defective supplier B-reps",
            "No Onshape document update, URDF regeneration or whole-arm cable sweep in this local candidate",
        ],
        "runtime": {
            p: importlib.metadata.version(p) for p in ("cadquery", "cadquery-ocp", "trimesh")
        },
        "physical_assembly_verified": False,
        "fabrication_approved": False,
    }
    report["outputs_sha256"] = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
    (out / "review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "window_spec",
                    "removed_volume_mm3",
                    "case_seats",
                    "contacts_counts",
                    "wire_sidewall_clearance_mm",
                    "wire_cover_clearance_mm",
                    "plug_straight_access_with_motor_installed_counts",
                )
            },
            indent=2,
        ),
        flush=True,
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.source, args.out)
