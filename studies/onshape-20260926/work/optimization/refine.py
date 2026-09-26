"""Resolve the measured compactness/wrist-travel tradeoff within the declared grid."""

import json
from dataclasses import replace

import numpy as np
from optimize import OUT, WRIST, mass_report, r5, source

from scripts.assembly_io import bounds
from scripts.id4_sweep_d405_r5 import MOVING, hits, id4_axis

parts = source()
upstream = {n: v for n, v in parts.items() if not n.startswith(MOVING)}
ub = {n: bounds(v) for n, v in upstream.items()}
point, axis, _ = id4_axis(parts)
search = json.loads((OUT / "reports/search.json").read_text())
report = []
for row in search["rendered_candidates"]:
    if row["kind"] != "central" or not row["bare_optics_pass"]:
        continue
    s = replace(r5.Spec(), glass_center=tuple(row["pose"]["glass"]), pitch_deg=row["pitch"])
    mount = r5.build(s)
    stop = None
    for degree in range(0, 132, 2):
        hit = hits(mount, upstream, ub, point, axis, degree, set(), True)
        if hit:
            stop = {"degree": degree, "hit": hit}
            break
    mass = mass_report(mount)
    record = {
        "id": row["id"],
        "positive_stop": stop,
        "mass": mass,
        "all_printed_single_valid": all(
            mount[n].isValid() and len(mount[n].Solids()) == 1
            for n in ["CAM5_BASE", "CAM5_D405_CARRIER"]
        ),
        "camera_radius_mm": float(np.linalg.norm(np.array(s.glass_center) - WRIST)),
    }
    report.append(record)
    (OUT / "reports/nearby.json").write_text(json.dumps(report, indent=2))
    print(
        row["id"],
        "stop",
        stop["degree"] if stop else None,
        "mass",
        round(mass["mass_g"], 2),
        "height",
        round(mass["height_above_motor_top_mm"], 2),
        "wrist",
        round(mass["wrist"]["pitch_gravity_amplitude_Nm"], 5),
        flush=True,
    )
