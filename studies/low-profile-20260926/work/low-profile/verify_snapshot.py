"""Verify archive bytes, skill copies, and optionally Git's staged contents."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / "work/gripper-low-profile"
DEST = REPO / "studies/low-profile-20260926"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    records = json.loads((DEST / "SNAPSHOT-MANIFEST.json").read_text())
    for item in records:
        assert sha(DEST / item["path"]) == item["sha256"], item["path"]
        assert sha(ROOT / item["path"]) == item["sha256"], item["path"]
    manifest = json.loads((REPO / "skills/onshape-workflow-snapshot.json").read_text())
    assert len(manifest["files"]) == 13
    for item in manifest["files"]:
        assert sha(REPO / "skills" / item["path"]) == item["sha256"]
        assert (
            sha(ROOT / "outputs/low-profile-250g/skills" / item["path"])
            == item["sha256"]
        )
        assert sha(Path(item["source"])) == item["sha256"]
    if args.staged:
        expected = [str((DEST / item["path"]).relative_to(REPO)) for item in records]
        expected += ["skills/" + item["path"] for item in manifest["files"]]
        expected += [
            "skills/ONSHAPE-WORKFLOW.md",
            "skills/onshape-workflow-snapshot.json",
        ]
        tracked = set(
            subprocess.check_output(["git", "ls-files", "-z"], cwd=REPO)
            .decode()
            .split("\0")
        )
        assert set(expected) <= tracked, sorted(set(expected) - tracked)
        for path in expected:
            staged = subprocess.check_output(["git", "show", ":" + path], cwd=REPO)
            assert hashlib.sha256(staged).hexdigest() == sha(REPO / path), path
    print(
        json.dumps(
            {
                "status": "PASS",
                "snapshot_files": len(records),
                "skill_source_files": 13,
                "git_staged_checked": args.staged,
            }
        )
    )


if __name__ == "__main__":
    main()
