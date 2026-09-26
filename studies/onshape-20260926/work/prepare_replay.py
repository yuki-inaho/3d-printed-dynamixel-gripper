import json
import shutil

from onshape_api import *

p = PRIVATE_ROOT / "replay"
d = json.loads((p / "document.json").read_text())
did = d["id"]
wid = d["defaultWorkspace"]["id"]
elements = api(f"/documents/d/{did}/w/{wid}/elements")
ps = next(
    e["id"] for e in elements if e["elementType"] == "PARTSTUDIO" and e["name"] != "Part Studio 1"
)
asm = next(e["id"] for e in elements if e["elementType"] == "ASSEMBLY")
project = {"did": did, "wid": wid, "ps": ps, "asm": asm}
(p / "project.json").write_text(json.dumps(project, indent=2))
parts = api(f"/parts/d/{did}/w/{wid}/e/{ps}")
assert len(parts) == 262, len(parts)
(p / "imported-parts.json").write_text(json.dumps(parts, indent=2))
for name in ["ps-specs.json", "asm-specs.json"]:
    shutil.copy2(PRIVATE_ROOT / name, p / name)
o = PRIVATE_ROOT.parent / "outputs/rebuild"
o.mkdir(exist_ok=True)
(o / "project.json").write_text(json.dumps(project, indent=2))
v = api(
    f"/documents/d/{did}/versions",
    "POST",
    {"documentId": did, "workspaceId": wid, "name": "V1 independent STEP import reference"},
)
(o / "reference-version.json").write_text(json.dumps(v, indent=2))
print(project, len(parts), "bodies")
