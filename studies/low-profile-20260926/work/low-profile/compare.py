"""Build physical camera supports for nondominated optical candidates."""

import json
import math
import sys
from dataclasses import asdict, replace

import numpy as np
from design import extended_arm, load_source, payload_delta
from paths import COMPACT_STEP, OPTIMIZATION
from study import OUT, save, target_center

sys.path.insert(0, str(OPTIMIZATION))
from mechanics import G, moment
from optimize import SHOULDER, WRIST, mass_report, overlaps, r5

from scripts.assembly_io import read_step


def candidate_spec(row):
    return replace(
        r5.Spec(),
        revision=row["id"],
        glass_center=tuple(row["pose"]["glass"]),
        pitch_deg=row["pitch"],
    )


def loading(mount, original, arm, extension):
    mass = mass_report(mount)
    items = [dict(v) for v in mass["items"]]
    changes = []
    for name in ["PG3_finger_L", "PG3_finger_R", "PG3_pad_L", "PG3_pad_R"]:
        density = 0.0011 if "pad_" in name else 0.00124
        old, new = original[name], arm[name]
        for sign, shape in [(-1, old), (1, new)]:
            changes.append(
                {
                    "name": name,
                    "signed_mass_kg": sign * shape.Volume() * density / 1000,
                    "com_mm": list(shape.Center().toTuple()),
                }
            )
    points = np.array(
        [i["com_mm"] for i in items]
        + [target_center(extension).tolist()]
        + [i["com_mm"] for i in changes]
    )
    masses = np.array(
        [i["mass_g"] / 1000 for i in items] + [0.25] + [i["signed_mass_kg"] for i in changes]
    )
    adjusted = {}
    for name, origin in [("wrist", WRIST), ("shoulder", SHOULDER)]:
        rel = (points - origin) / 1000
        sy, sz = [float((masses * rel[:, i]).sum()) for i in [1, 2]]
        adjusted[name] = {
            "reference_abs_Mx_Nm": abs(float(moment(points, masses, origin)[0])),
            "pitch_amplitude_Nm": G * math.hypot(sy, sz),
        }
    return {
        "camera_group": mass,
        "added_finger_pad_mass_g": 1000 * sum(i["signed_mass_kg"] for i in changes),
        "signed_finger_pad_changes": changes,
        "payload_only_increment_Nm": payload_delta(extension),
        "partial_load_including_finger_pad_delta": adjusted,
        "included": "camera group + 250g payload + finger/pad delta from baseline; excludes unchanged arm and gripper mass",
        "finger_uniform_beam_stress_ratio": (16.7 + extension) / 16.7,
        "finger_uniform_beam_deflection_ratio": ((16.7 + extension) / 16.7) ** 3,
        "physical_strength_verified": False,
    }


def main():
    rows = json.loads((OUT / "reports/optical-shortlist.json").read_text())

    def vector(r):
        return np.array(
            [
                r["pitch"],
                r["extension_mm"],
                r["pose"]["glass"][1],
                r["pose"]["glass"][2],
            ]
        )

    # This is an explicit geometric screening subset, not a claim of full-mass Pareto optimality.
    shortlist = [
        r
        for r in rows
        if not any(np.all(vector(q) <= vector(r)) and np.any(vector(q) < vector(r)) for q in rows)
    ]
    print("physical subset", len(shortlist), [r["id"] for r in shortlist], flush=True)
    original = load_source()
    compact = {r.name: r.world for r in read_step(COMPACT_STEP)[2] if r.name.startswith("CAM5_")}
    baseline_hits = overlaps(compact, original)
    baseline_within = overlaps(compact, compact, True)
    baseline = loading(compact, original, original, 0)
    known = {(r["a"], r["b"], r["type"]) for r in baseline_hits}
    known_internal = {(r["a"], r["b"], r["type"]) for r in baseline_within}
    result = {
        "selection_scope": "nondominated pitch/extension/glass Y/glass Z from full optical grid; not full mechanical global optimum",
        "baseline": baseline,
        "baseline_hits": baseline_hits,
        "baseline_within_mount": baseline_within,
        "candidates": [],
    }
    arms = {}
    for row in shortlist:
        record = {
            k: row[k] for k in ["id", "pitch", "extension_mm", "pose", "minimum_cube_visible"]
        }
        try:
            spec = candidate_spec(row)
            mount = r5.build(spec)
            extension = row["extension_mm"]
            if extension not in arms:
                arms[extension] = extended_arm(original, extension)
            arm = arms[extension]
            valid = {
                n: {"valid": mount[n].isValid(), "solids": len(mount[n].Solids())}
                for n in ["CAM5_BASE", "CAM5_D405_CARRIER"]
            }
            outer = overlaps(mount, arm)
            internal = overlaps(mount, mount, True)
            new_outer = [r for r in outer if (r["a"], r["b"], r["type"]) not in known]
            new_internal = [
                r for r in internal if (r["a"], r["b"], r["type"]) not in known_internal
            ]
            record.update(
                {
                    "spec": asdict(spec),
                    "validity": valid,
                    "loads": loading(mount, original, arm, extension),
                    "hits": outer,
                    "within_mount": internal,
                    "new_outer": new_outer,
                    "new_internal": new_internal,
                    "static_candidate_pass": all(
                        v["valid"] and v["solids"] == 1 for v in valid.values()
                    )
                    and not new_outer
                    and not new_internal,
                }
            )
        except Exception as exc:  # noqa: BLE001 -- keep failed CAD candidates in the report.
            record.update({"error": str(exc), "static_candidate_pass": False})
        result["candidates"].append(record)
        save("physical-comparison.json", result)
        print(
            record["id"],
            "pass",
            record["static_candidate_pass"],
            "height",
            round(
                record.get("loads", {}).get("camera_group", {}).get("height_above_motor_top_mm", 0),
                2,
            ),
            "new hits",
            record.get("new_outer"),
            record.get("new_internal"),
            record.get("error", ""),
            flush=True,
        )


if __name__ == "__main__":
    main()
