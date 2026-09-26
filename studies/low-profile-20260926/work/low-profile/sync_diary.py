"""Save the full workdoc, review and handoff under the repository's diary/."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/low-profile-250g"
DEST = ROOT / "work/gripper-low-profile/diary"


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    mapping = {
        "WORKDOC.md": "workdoc_Sep26-2026_low_profile_d405.md",
        "final-review.md": "review_Sep26-2026_low_profile_d405.md",
        "HANDOFF.md": "handoff_Sep26-2026_low_profile_d405.md",
    }
    records = []
    for source, name in mapping.items():
        content = (OUT / source).read_text()
        if source == "HANDOFF.md":

            def relocate(match):
                target = match.group(1)
                if target.startswith(("http://", "https://", "#")):
                    return match.group(0)
                return (
                    "]("
                    + "../studies/low-profile-20260926/outputs/low-profile-250g/"
                    + target
                    + ")"
                )

            content = re.sub(r"\]\(([^)]+)\)", relocate, content)
        target = DEST / name
        target.write_text(content)
        records.append(
            {
                "path": name,
                "source": str((OUT / source).relative_to(ROOT)),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    (DEST / "onshape-low-profile-20260926-manifest.json").write_text(
        json.dumps(records, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "diary_files": len(records),
                "workdoc_byte_identical": (DEST / mapping["WORKDOC.md"]).read_bytes()
                == (OUT / "WORKDOC.md").read_bytes(),
            }
        )
    )


if __name__ == "__main__":
    main()
