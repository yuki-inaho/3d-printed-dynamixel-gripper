"""Copy explicitly scoped study artifacts and inspect content before Git staging."""

import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "work/gripper-low-profile/studies/low-profile-20260926"
PATTERN = re.compile(
    rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|(?:sk-proj-|gh[pousr]_)[A-Za-z0-9_-]{20,}|(?:ONSHAPE_ACCESS_KEY|ONSHAPE_SECRET_KEY)\s*[:=]\s*['\"]?[A-Za-z0-9]{20,}"
)
FORBIDDEN = {".env", "storage-state.json", "auth.json", "cookies.json"}


def check(data, label):
    if PATTERN.search(data):
        raise ValueError(f"Potential secret: {label}")


def main():
    records = []
    # These are live coordinator state, not reproducible deliverables. The full
    # chronological record and pending checklist remain in WORKDOC/HANDOFF.
    state_names = {"active-item.json", "suspended-item.json"}
    for name in state_names:
        stale = DEST / "work/low-profile" / name
        if stale.exists():
            stale.unlink()
    for scope in ("outputs/low-profile-250g", "work/low-profile"):
        for path in sorted((ROOT / scope).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.suffix in {".pyc", ".pyo"}:
                continue
            if path.name in state_names:
                continue
            if path.name in FORBIDDEN or path.is_symlink():
                raise ValueError(f"Forbidden archive input: {path.name}")
            data = path.read_bytes()
            check(data, path.name)
            if path.suffix == ".zip":
                with zipfile.ZipFile(path) as archive:
                    for item in archive.infolist():
                        check(archive.read(item), item.filename)
            relative = path.relative_to(ROOT)
            target = DEST / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            records.append(
                {
                    "path": str(relative),
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
    (DEST / "SNAPSHOT-MANIFEST.json").write_text(json.dumps(records, indent=2) + "\n")
    print(
        json.dumps(
            {
                "files": len(records),
                "bytes": sum(x["bytes"] for x in records),
                "secret_scan": "PASS_SCOPED_PATTERNS_INCLUDING_ZIP",
            }
        )
    )


if __name__ == "__main__":
    main()
