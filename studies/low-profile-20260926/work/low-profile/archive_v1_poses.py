"""Keep rejected pre-repair pose exports separate from current validation inputs."""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "outputs/low-profile-250g"
poses = OUT / "CAD/native-poses"
reports = OUT / "reports"
archive = poses / "diagnostics/v1-pad-misassigned"
archive.mkdir(parents=True, exist_ok=False)
report_archive = reports / "v1-pad-misassigned"
report_archive.mkdir(exist_ok=False)
mapping = {}
for f in poses.glob("*.step"):
    dest = archive / f.name
    mapping[str(f.resolve())] = str(dest.resolve())
    f.rename(dest)
for f in reports.glob("native-step-*.json"):
    if f.name in (
        "native-step-geometry-diagnostic.json",
        "native-step-version-yaw10-exported-zero.json",
    ):
        continue
    data = json.loads(f.read_text())
    if data.get("input") in mapping:
        data["input"] = mapping[data["input"]]
    data["status"] = "SUPERSEDED_PAD_MEMBERSHIP_REPAIRED_IN_NEXT_VERSION"
    (report_archive / f.name).write_text(json.dumps(data, indent=2) + "\n")
    f.unlink()
f = reports / "native-pose-transforms.json"
f.rename(report_archive / f.name)
f = reports / "ui-export-manifest.json"
data = json.loads(f.read_text())
for e in data["exports"]:
    if e["path"] in mapping:
        e["path"] = mapping[e["path"]]
        e["accepted_for_native_pose"] = False
        e["reason"] = (
            "Superseded: PG3_pad_L/R followed opposite jaw in pre-repair assembly"
        )
f.write_text(json.dumps(data, indent=2) + "\n")
print("Archived", len(mapping), "STEP files and corresponding evidence")
