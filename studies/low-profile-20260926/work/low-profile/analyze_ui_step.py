"""Inspect XCAF names and placements from an actual browser-downloaded STEP."""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "work/gripper-low-profile/scripts")
)
from assembly_io import bounds, read_step

parser = argparse.ArgumentParser()
parser.add_argument("step", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
raw = args.step.read_bytes()
doc, shape_tool, rows = read_step(args.step)
items = []
for row in rows:
    tr = row.loc.wrapped.Transformation()
    matrix = [[tr.Value(i, j) for j in range(1, 5)] for i in range(1, 4)] + [
        [0, 0, 0, 1]
    ]
    items.append(
        {
            "index": row.index,
            "name": row.name,
            "path": row.path,
            "placement_mm": matrix,
            "local_bounds_mm": bounds(row.shape),
            "world_bounds_mm": bounds(row.world),
            "solids": len(row.shape.Solids()),
            "shells": len(row.shape.Shells()),
            "faces": len(row.shape.Faces()),
            "volume_mm3": sum(s.Volume() for s in row.shape.Solids())
            if row.shape.Solids()
            else None,
            "area_mm2": row.shape.Area(),
        }
    )
result = {
    "input": str(args.step.resolve()),
    "sha256": hashlib.sha256(raw).hexdigest(),
    "bytes": len(raw),
    "step_si_units": sorted(
        set(re.findall(r"SI_UNIT\([^;]+", raw.decode(errors="replace")))
    ),
    "reader_length_unit": "mm (OCCT default target unit)",
    "occurrences": len(items),
    "solid_count": sum(x["solids"] for x in items),
    "by_parent": dict(Counter(x["path"].rsplit("/", 1)[0] for x in items)),
    "parts": items,
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "parts"}, indent=2))
print("first names", [x["name"] for x in items[:8]])
print("last names", [x["name"] for x in items[-8:]])
