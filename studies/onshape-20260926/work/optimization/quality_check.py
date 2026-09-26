"""Read-only final quality checks, except deterministic validation/report output."""

import datetime
import hashlib
import json
import re
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/optimization-250g"
PROJECT = "/home/inaho-omen/Project/3d-printed-dynamixel-gripper"
UV = ["uv", "run", "--project", PROJECT, "--no-sync"]
checks = []


def record(name, passed, **evidence):
    checks.append({"name": name, "pass": bool(passed), **evidence})


def command(name, args, cwd=ROOT):
    result = subprocess.run(
        ["rtk", "proxy", *args], cwd=cwd, text=True, capture_output=True, check=False
    )
    record(name, result.returncode == 0, exit=result.returncode, output=result.stdout)
    return result


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


targets = [
    "work/optimization",
    "outputs/optimization-250g/robot/pg3_states.py",
    "outputs/optimization-250g/robot/validate_robot.py",
]
command("ruff-check", [*UV, "ruff", "check", *targets])
command("ruff-format", [*UV, "ruff", "format", "--check", *targets])
command("pytest", [*UV, "pytest", "work/optimization/test_mechanics.py", "-q"])
command("urdf-validation", [sys.executable, str(OUT / "robot/validate_robot.py")])

missing = []
markdown_files = list(OUT.rglob("*.md")) + [
    ROOT / "outputs/README.md",
    ROOT / "outputs/WORKLOG.md",
]
for path in markdown_files:
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if target.startswith(("https://", "http://", "#", "mailto:")):
            continue
        clean = unquote(target.strip("<>").split("#", 1)[0])
        if clean and not (path.parent / clean).exists():
            missing.append({"file": str(path.relative_to(ROOT)), "target": target})
record("local-links", not missing, missing=missing)

manifest = json.loads((OUT / "robot/source-manifest.json").read_text())
hash_errors = []
if sha(OUT / "CAD/Robot_250g_compact_D405.step") != manifest["source_sha256"]:
    hash_errors.append("CAD")
for name, key in [
    ("robot.urdf", "portable_urdf_sha256"),
    ("robot.onshape-raw.urdf", "raw_urdf_sha256"),
]:
    if sha(OUT / "robot" / name) != manifest[key]:
        hash_errors.append(name)
for name, item in manifest["meshes"].items():
    if sha(OUT / "robot/assets" / name) != item["sha256"]:
        hash_errors.append(name)
record("source-and-export-hashes", not hash_errors, failures=hash_errors)

for repo in ["/home/inaho-omen/Project/low_cost_robot", PROJECT]:
    result = subprocess.run(
        ["rtk", "proxy", "git", "status", "--porcelain"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    record(
        "source-repo",
        result.returncode == 0 and not result.stdout.strip(),
        path=repo,
        status=result.stdout,
    )
    command("source-repo-whitespace", ["git", "diff", "--check"], Path(repo))

texts = [p for p in OUT.rglob("*") if p.suffix in {".md", ".py", ".json"}]
texts += list((ROOT / "work/optimization").glob("*.py"))
texts += [ROOT / "outputs/README.md", ROOT / "outputs/WORKLOG.md"]
whitespace = []
for path in texts:
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
        text=True,
        capture_output=True,
        check=False,
    )
    if result.stdout or result.stderr or result.returncode not in (0, 1):
        whitespace.append(
            {"path": str(path.relative_to(ROOT)), "output": result.stdout}
        )
record("whitespace", not whitespace, failures=whitespace)

cache = json.loads((ROOT / "work/cache/manifest.json").read_text())
record(
    "content-cache",
    all(sha(ROOT / row["cache"]) == row["sha256"] for row in cache["entries"]),
    entries=len(cache["entries"]),
)
private_paths = [
    ROOT / "work/onshape-key-private.json",
    ROOT / "work/cache/onshape/private/onshape.auth-state.json",
    ROOT / "work/cache/onshape/private",
    ROOT / "work/cache/onshape/profile",
]
modes = [stat.S_IMODE(p.stat().st_mode) for p in private_paths]
record("private-permissions", modes == [0o600, 0o600, 0o700, 0o700], modes=modes)

# Never log credential or cookie values; only report filenames on a match.
keys = json.loads(private_paths[0].read_text())
secrets = [
    value
    for name, value in keys.items()
    if re.search(r"secret|access|token", name, re.IGNORECASE)
    and isinstance(value, str)
    and len(value) > 20
]
auth = json.loads(private_paths[1].read_text())
secrets += [c["value"] for c in auth["cookies"] if len(c["value"]) > 24]
leaks = []
for path in (ROOT / "outputs").rglob("*"):
    if path.suffix not in {".md", ".json", ".py", ".html", ".urdf", ".txt"}:
        continue
    content = path.read_text(errors="replace")
    if any(secret in content for secret in secrets):
        leaks.append(str(path.relative_to(ROOT)))
record("private-state-excluded", not leaks and len(secrets) > 0, matching_files=leaks)

required = [
    "REPORT.md",
    "MANUAL.md",
    "MANUAL.html",
    "MANUAL.pdf",
    "HEADLESS.md",
    "WORKDOC.md",
    "workdoc-review.md",
    "robot/README.md",
    "robot/native-reference.json",
    "robot/robot.urdf",
    "robot/robot.onshape-raw.urdf",
    "robot/validation.json",
    "reports/native-motion.json",
    "reports/native-assembly.json",
    "reports/export-provenance.json",
    "reports/manual-final-verification.json",
    "images/onshape-08-animate.png",
    "images/onshape-09-motion-interference.png",
]
record(
    "artifacts",
    all((OUT / p).is_file() and (OUT / p).stat().st_size > 0 for p in required)
    and len(list((OUT / "robot/assets").glob("*.stl"))) == 12,
    required=required,
    mesh_files=12,
)
manual = json.loads((OUT / "reports/manual-final-verification.json").read_text())
record(
    "manual-verified-hashes",
    all(sha(OUT / name) == value for name, value in manual["sha256"].items()),
    pages=manual["pdf_pages"],
    images=manual["embedded_images"],
)
skill = Path("/home/inaho-omen/.codex/skills/onshape-robot-workflow")
record(
    "skill-copy",
    all(
        (ROOT / "outputs/onshape-robot-workflow" / p.relative_to(skill)).read_bytes()
        == p.read_bytes()
        for p in skill.rglob("*")
        if p.is_file()
    ),
)
report = {
    "time": datetime.datetime.now().astimezone().isoformat(),
    "pass": all(row["pass"] for row in checks),
    "checks": checks,
}
(OUT / "reports/quality-motion-final.json").write_text(json.dumps(report, indent=2))
print(
    json.dumps(
        {
            "pass": report["pass"],
            "checks": len(checks),
            "failed": [r for r in checks if not r["pass"]],
        },
        indent=2,
    )
)
raise SystemExit(0 if report["pass"] else 1)
