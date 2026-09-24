import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import jointspace_safety_report as jsr  # noqa: E402
import replay_poses as rp  # noqa: E402


def test_parse_fractions_for_custom_grid():
    assert rp._parse_fractions("-0.6,-0.3,0,0.3,0.6") == (
        -0.6, -0.3, 0.0, 0.3, 0.6)


def test_jointspace_safety_report_groups_replay_results():
    doc = {
        "model": "dummy.xml",
        "thresholds": {"penetration_mm": 2.0, "tracking_rad": 0.2},
        "poses": [
            {"target": [0.0, -1.0, 0.0], "ok": True, "reachable": True,
             "no_self_collision": True, "self_interference_mm": 0.0,
             "self_pair": None},
            {"target": [0.0, -1.0, 1.0], "ok": False, "reachable": True,
             "no_self_collision": False, "self_interference_mm": 3.0,
             "self_pair": ["wrist", "shoulder"]},
            {"target": [0.0, 0.0, 1.0], "ok": False, "reachable": False,
             "no_self_collision": True, "self_interference_mm": 0.0,
             "self_pair": None},
        ],
    }

    report = jsr.analyze(
        doc,
        joint_names=["j1", "j2", "j3"],
        focus_indexes=[1, 2],
    )

    assert report["summary"]["total"] == 3
    assert report["summary"]["lost"] == 2
    assert report["reason_counts"]["self_collision"] == 1
    assert report["reason_counts"]["tracking"] == 1
    assert report["lost_pair_counts"]["wrist <-> shoulder"] == 1
    assert report["lost_pair_counts"]["(none)"] == 1
    assert report["per_joint"]["j2"][0]["level"] == -1.0
    assert report["focus_groups_by_risk"][0]["lost_rate"] == 1.0

    md = jsr.render_markdown(report)
    assert "Joint-Space Safety Report" in md
    assert "wrist <-> shoulder" in md
