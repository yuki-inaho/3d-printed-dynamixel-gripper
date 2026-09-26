"""Compare saved source geometry with the UI version STEP; preserve raw deltas."""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "work/gripper-low-profile/scripts"))
from assembly_io import bounds, read_step

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/low-profile-250g"
source = OUT / "CAD/Robot_250g_low_profile_D405.step"
doc, shape_tool, rows = read_step(source)
native = json.loads((OUT / "reports/native-step-zero.json").read_text())
source_groups = defaultdict(list)
native_groups = defaultdict(list)
for row in rows:
    shape = row.world
    source_groups[row.name].append(
        {
            "bounds": bounds(shape),
            "volume": sum(s.Volume() for s in shape.Solids()),
            "area": shape.Area(),
            "solids": len(shape.Solids()),
        }
    )
for row in native["parts"]:
    native_groups[row["name"]].append(
        {
            "bounds": row["world_bounds_mm"],
            "volume": row["volume_mm3"] or 0,
            "area": row["area_mm2"],
            "solids": row["solids"],
        }
    )


def aggregate(items):
    b = np.array([x["bounds"] for x in items])
    return {
        "bounds": np.r_[b[:, :3].min(axis=0), b[:, 3:].max(axis=0)].tolist(),
        "volume": sum(x["volume"] for x in items),
        "area": sum(x["area"] for x in items),
        "solids": sum(x["solids"] for x in items),
    }


assert source_groups.keys() == native_groups.keys(), "Part names differ"
comparisons = []
for name in source_groups:
    a = aggregate(source_groups[name])
    b = aggregate(native_groups[name])
    comparisons.append(
        {
            "name": name,
            "source": a,
            "native": b,
            "max_bbox_delta_mm": float(np.abs(np.array(a["bounds"]) - b["bounds"]).max()),
            "volume_delta_mm3": b["volume"] - a["volume"],
            "area_delta_mm2": b["area"] - a["area"],
        }
    )
expected = json.loads((OUT / "reports/expected-groups.json").read_text())["groups"]
mapping = {}
for group, parts in expected.items():
    for part in parts:
        assert part["name"] not in mapping or mapping[part["name"]] == group
        mapping[part["name"]] = group
actual = Counter((p["name"], "solid" if p["solids"] else "sheet") for p in native["parts"])
desired = Counter((p["name"], p["body_type"]) for parts in expected.values() for p in parts)
assert actual == desired, {
    "unexpected": str(actual - desired),
    "missing": str(desired - actual),
}
result = {
    "source": str(source),
    "native_step_sha256": native["sha256"],
    "names_and_body_types_match": True,
    "native_bodies_by_declared_group": dict(Counter(mapping[p["name"]] for p in native["parts"])),
    "group_assignment_evidence": "Name mapping checked; common motion of members still requires posed STEP files.",
    "max_bbox_delta_mm": max(x["max_bbox_delta_mm"] for x in comparisons),
    "max_abs_volume_delta_mm3": max(abs(x["volume_delta_mm3"]) for x in comparisons),
    "max_abs_area_delta_mm2": max(abs(x["area_delta_mm2"]) for x in comparisons),
    "scope": "Inventory, bounds, volume and area comparison, not a full symmetric-difference proof.",
    "parts": comparisons,
}
(OUT / "reports/native-zero-source-comparison.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "parts"}, indent=2))
