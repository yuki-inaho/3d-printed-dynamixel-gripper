"""Check delivered evidence without network calls or printing private values."""

import hashlib
import json
import re
import stat
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from urllib.parse import unquote

from checkpoint import PATTERN

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/low-profile-250g"


def main():
    checks = []

    def record(name, passed, **details):
        checks.append({"name": name, "pass": bool(passed), **details})

    missing = []
    for path in OUT.rglob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if target.startswith(("https://", "http://", "#", "mailto:")):
                continue
            clean = unquote(target.strip("<>").split("#", 1)[0])
            if clean and not (path.parent / clean).exists():
                missing.append({"source": str(path.relative_to(OUT)), "target": target})
    record("local-links", not missing, missing=missing)
    for name, count in (("final-cad-tests.xml", 18), ("final-converter-tests.xml", 17)):
        suite = ET.parse(OUT / "reports" / name).getroot().find("testsuite")
        attrs = suite.attrib
        record(
            name,
            int(attrs["tests"]) == count
            and int(attrs["failures"]) == 0
            and int(attrs["errors"]) == 0,
            tests=int(attrs["tests"]),
        )
    native = json.loads((OUT / "robot/validation.json").read_text())
    record(
        "new-urdf-validation",
        native["status"] == "PASS_KINEMATIC_ONLY"
        and native["native_pose_cases"] == 11
        and native["sampled_configurations"] == 441
        and native["occurrences"] == 262,
    )
    record(
        "version-step-hash",
        hashlib.sha256((OUT / "CAD/final-version.step").read_bytes()).hexdigest()
        == native["input_sha256"],
    )
    manual = json.loads((OUT / "reports/manual-final-verification.json").read_text())
    record(
        "manual",
        manual["status"] == "PASS" and manual["pdf_pages"] == 20,
        images=len(manual["images"]),
    )
    required = [
        "MANUAL.md",
        "MANUAL.html",
        "MANUAL.pdf",
        "REPORT.md",
        "CONVERTER.md",
        "API-USAGE.md",
        "final-review.md",
        "robot/model/robot.urdf",
        "robot/validation.json",
        "robot/converter-config.json",
    ]
    record(
        "artifacts",
        all((OUT / name).is_file() and (OUT / name).stat().st_size > 0 for name in required)
        and len(list((OUT / "robot/model/assets").glob("*.stl"))) == 12,
    )
    private = ROOT / "work/cache/onshape/private/onshape.auth-state.json"
    keyfile = ROOT / "work/onshape-key-private.json"
    keys = json.loads(keyfile.read_text())
    values = [
        v.encode()
        for k, v in keys.items()
        if re.search(r"secret|access|token", k, re.IGNORECASE)
        and isinstance(v, str)
        and len(v) > 20
    ]
    auth = json.loads(private.read_text())
    values += [c["value"].encode() for c in auth["cookies"] if len(c["value"]) > 24]
    assert values, "No private-value checks available"
    leaks = []
    paths = list(OUT.rglob("*")) + list((ROOT / "work/low-profile").rglob("*"))
    for path in paths:
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        payloads = [(str(path.relative_to(ROOT)), path.read_bytes())]
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                payloads += [
                    (f"{path.name}:{item.filename}", archive.read(item))
                    for item in archive.infolist()
                ]
        for label, payload in payloads:
            if PATTERN.search(payload) or any(value in payload for value in values):
                leaks.append(label)
    record("private-values-and-secret-patterns", not leaks, matching_files=leaks)
    modes = [
        stat.S_IMODE(path.stat().st_mode)
        for path in (
            keyfile,
            private,
            private.parent,
            ROOT / "work/cache/onshape/profile",
        )
    ]
    record("private-permissions", modes == [0o600, 0o600, 0o700, 0o700], modes=modes)
    record(
        "api-counter",
        (ROOT / "work/api-count.txt").read_text().strip() == "526",
        direct_calls_this_study=0,
    )
    whitespace = []
    for path in paths:
        if path.suffix not in {".py", ".md", ".json", ".js", ".yaml"} or not path.is_file():
            continue
        result = subprocess.run(
            [
                "rtk",
                "proxy",
                "git",
                "diff",
                "--no-index",
                "--check",
                "/dev/null",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout or result.stderr or result.returncode not in (0, 1):
            whitespace.append(str(path.relative_to(ROOT)))
    record("git-diff-check-text", not whitespace, failures=whitespace)
    for repo in ("low_cost_robot", "3d-printed-dynamixel-gripper"):
        path = Path("LOCAL_HOME/Project") / repo
        result = subprocess.run(
            ["rtk", "proxy", "git", "status", "--porcelain"],
            cwd=path,
            capture_output=True,
            text=True,
            check=False,
        )
        lines = result.stdout.splitlines()
        tracked_changes = [line for line in lines if not line.startswith("?? ")]
        record(
            f"original-tracked-source-{repo}",
            result.returncode == 0 and not tracked_changes,
            external_untracked=[line[3:] for line in lines if line.startswith("?? ")],
            handling="Unrelated untracked user work is preserved and excluded from this task's commits",
        )
    report = {
        "status": "PASS" if all(check["pass"] for check in checks) else "FAIL",
        "checks": checks,
    }
    (OUT / "reports/final-quality.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
