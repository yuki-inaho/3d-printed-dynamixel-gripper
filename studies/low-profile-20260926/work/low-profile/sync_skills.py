"""Save only this task's four skill trees; preserve unrelated repository skills."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("/home/inaho-omen/.codex/skills")
NAMES = (
    "onshape-robot-workflow",
    "write-workdoc-uv",
    "review-written-workdoc",
    "start-work-with-docs",
)
REPO = ROOT / "work/gripper-low-profile/skills"
OUT = ROOT / "outputs/low-profile-250g/skills"


def main():
    records = []
    for name in NAMES:
        for source in sorted((SOURCE / name).rglob("*")):
            if not source.is_file() or "__pycache__" in source.parts:
                continue
            assert not source.is_symlink()
            relative = source.relative_to(SOURCE)
            for destination in (REPO, OUT):
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                assert target.read_bytes() == source.read_bytes()
            records.append(
                {
                    "path": str(relative),
                    "source": str(source),
                    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                }
            )
    manifest = {
        "scope": list(NAMES),
        "files": records,
        "policy": "Source user-local skills; Onshape updated with demonstrated task findings; no browser credentials",
    }
    for destination in (REPO, OUT):
        (destination / "onshape-workflow-snapshot.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
    shutil.copy2(OUT / "ONSHAPE-WORKFLOW.md", REPO / "ONSHAPE-WORKFLOW.md")
    print(
        json.dumps(
            {
                "skills": len(NAMES),
                "source_files": len(records),
                "destinations": [str(REPO), str(OUT)],
            }
        )
    )


if __name__ == "__main__":
    main()
