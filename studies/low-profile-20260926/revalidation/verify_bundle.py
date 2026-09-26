"""Verify the delivered file set using only Python's standard library."""

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

IGNORED_DIRECTORIES = {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
MANIFEST = "BUNDLE-MANIFEST.json"


def files(root):
    return {
        p.relative_to(root).as_posix(): p
        for p in root.rglob("*")
        if p.is_file()
        and not (set(p.relative_to(root).parts) & IGNORED_DIRECTORIES)
        and p.relative_to(root).as_posix() != MANIFEST
    }


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    expected = {}
    errors = []
    for item in manifest["files"]:
        name = item["path"]
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or name in expected:
            raise ValueError(f"Unsafe or duplicate manifest path: {name}")
        expected[name] = item
    actual = files(root)
    for name in sorted(expected.keys() - actual.keys()):
        errors.append(f"missing: {name}")
    for name in sorted(actual.keys() - expected.keys()):
        errors.append(f"unlisted: {name}")
    for name in sorted(actual.keys() & expected.keys()):
        path, record = actual[name], expected[name]
        if path.is_symlink():
            errors.append(f"unexpected symlink: {name}")
            continue
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if path.stat().st_size != record["bytes"] or digest != record["sha256"]:
            errors.append(f"changed: {name}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "files_expected": len(expected),
        "files_found": len(actual),
        "errors": errors,
        "note": "Integrity only, not a signature or fabrication approval; runtime caches ignored",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()
    try:
        result = verify(args.root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "PASS" else 1
    except (ValueError, KeyError, OSError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
