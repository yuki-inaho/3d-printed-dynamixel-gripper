"""Populate only the dedicated 250g study document with fixed inspection instances."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "work"))
from onshape_api import api

P = ROOT / "work/optimization/onshape"
project = json.loads((P / "project.json").read_text())
did, wid, ps, asm = (project[k] for k in ("did", "wid", "ps", "asm"))
assert did == "7b85d8922959cbe564b6e0cb"
parts = [
    p for p in json.loads((P / "composite-parts.json").read_text()) if p["bodyType"] == "composite"
]
names = list(json.loads((P / "composites.json").read_text()))
assert len(parts) == len(names) == 12
ledger = P / "static-instances.json"
instances = json.loads(ledger.read_text()) if ledger.exists() else {}
for name, part in zip(names, parts):
    if name in instances:
        continue
    api(
        f"/metadata/d/{did}/w/{wid}/e/{ps}/p/{part['partId']}",
        "POST",
        {"properties": [{"propertyId": "57f3fb8efa3416c06701d60d", "value": name}]},
    )
    result = api(
        f"/assemblies/d/{did}/w/{wid}/e/{asm}/instances",
        "POST",
        {
            "documentId": did,
            "elementId": ps,
            "partId": part["partId"],
            "isAssembly": False,
            "isFixed": True,
        },
    )
    instances[name] = result
    ledger.write_text(json.dumps(instances, indent=2))
    print("inserted fixed", name, flush=True)
for eid, name in [
    (ps, "Compact D405 - Rigid Groups"),
    (asm, "Compact D405 - Static Validation"),
]:
    api(
        f"/metadata/d/{did}/w/{wid}/e/{eid}",
        "POST",
        {"properties": [{"propertyId": "57f3fb8efa3416c06701d60d", "value": name}]},
    )
assembly = api(f"/assemblies/d/{did}/w/{wid}/e/{asm}", query={"includeNonSolids": "true"})
(P / "static-assembly.json").write_text(json.dumps(assembly, indent=2))
assert len(assembly["rootAssembly"]["instances"]) == 12
print("static assembly 12 instances saved")
