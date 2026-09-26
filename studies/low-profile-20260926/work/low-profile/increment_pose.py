"""Retry one failed UI pose via explicit, checked intermediate positions."""

import argparse
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "outputs/low-profile-250g"
parser = argparse.ArgumentParser()
parser.add_argument("name")
parser.add_argument("--increment", type=float, default=10)
args = parser.parse_args()
targets = json.loads((OUT / "reports/native-pose-targets.json").read_text())["cases"]
target = next(r for r in targets if r["name"] == args.name)
values = list(target["expected_deg"].values())
col = next(i for i, v in enumerate(values) if v)
spec = {"name": args.name, "col": col, "deg": values[col], "increment": args.increment}
script = HERE / "current-increment.js"
script.write_text(
    (HERE / "increment-pose.template.js").read_text().replace("__CASE__", json.dumps(spec))
)
proc = subprocess.run(
    [
        "rtk",
        "proxy",
        "npx",
        "--yes",
        "@playwright/cli",
        "-s=onshape-headless",
        "run-code",
        "--filename=low-profile/current-increment.js",
    ],
    cwd=ROOT / "work",
    capture_output=True,
    text=True,
    timeout=1800,
    check=False,
)
raw = proc.stdout + proc.stderr
(HERE / "ui-logs" / f"{args.name}-increment.txt").write_text(raw)
if proc.returncode or "### Error" in raw:
    raise RuntimeError(raw[-3500:])
result = json.loads(raw.split("### Result\n", 1)[1].split("\n###", 1)[0])
assert result["stored_deg"] == values
p = OUT / "reports/native-ui-poses.json"
report = json.loads(p.read_text())
if "failed_case" in report:
    report.setdefault("failure_history", []).append(
        {
            "case": report.pop("failed_case"),
            "error": report.pop("error"),
            "resolution": "UI incremental pose",
        }
    )
report["cases"].append(result)
report["status"] = "RUNNING"
p.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(result, indent=2), flush=True)
