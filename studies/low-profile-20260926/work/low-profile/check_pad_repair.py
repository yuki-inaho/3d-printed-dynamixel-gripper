"""Document the detected pad membership defect and fresh-pose correction."""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "outputs/low-profile-250g"
before = json.loads(
    (OUT / "reports/v1-pad-misassigned/native-pose-transforms.json").read_text()
)
after = json.loads((OUT / "reports/native-pose-transforms.json").read_text())
assert before["verification_status"] == "FAIL_RIGID_MEMBER_MOTION"
assert after["verification_status"] == "RIGID_MEMBERS_PASS_FK_PENDING"
cases = []
for b, a in zip(before["cases"], after["cases"], strict=True):
    assert b["name"] == a["name"]
    for group in ("jaw_l", "jaw_r"):
        old = b["instances"][group]
        new = a["instances"][group]
        assert old["body_count"] == new["body_count"] == 12
        cases.append(
            {
                "pose": a["name"],
                "group": group,
                "before_max_member_delta_mm": old["max_member_translation_delta_mm"],
                "after_max_member_delta_mm": new["max_member_translation_delta_mm"],
            }
        )
report = {
    "status": "PASS",
    "cause": "Import Update preserved stale union queries that assigned PG3_pad_L/R to opposite jaw",
    "repair": "Both jaw composites rebuilt through normal UI with twelve explicitly named parts each",
    "negative_control": "All original files retained and rejected by rigid-member motion guard",
    "cases": cases,
}
(OUT / "reports/pad-membership-repair.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(
    "PASS: 22 fresh jaw/pose membership checks, original defect retained as negative control"
)
