import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
state = root / "reproduction-smoke"
state.mkdir(exist_ok=True)
(state / "project.json").write_text((root / "replay/project.json").read_text())
key = json.loads((root / "onshape-key-private.json").read_text())["data"]
os.environ.update(
    ONSHAPE_TASK_WORK=str(state),
    ONSHAPE_TASK_OUTPUT=str(state / "outputs"),
    ONSHAPE_ACCESS_KEY=key["accessKey"],
    ONSHAPE_SECRET_KEY=key["secretKey"],
)
scripts = root.parent / "outputs/reproduce"
for path in scripts.glob("*.py"):
    compile(path.read_text(), str(path), "exec")
sys.path.insert(0, str(scripts))
from onshape_api import DID, api

r = api("/documents/" + DID)
assert r["public"] is True
print("Distribution helper signed-read smoke: PASS; document public=true")
