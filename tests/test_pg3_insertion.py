import cadquery as cq
import pytest

from scripts.review_pg3_insertion import sample_translation


def test_clear_endpoints_do_not_hide_path_collision():
    part = cq.Solid.makeBox(1, 1, 1)
    obstacle = cq.Solid.makeBox(1, 1, 1, (5, 0, 0))
    report = sample_translation({"part": part}, {"obstacle": obstacle}, (10, 0, 0))
    assert not report["samples"][0]["unresolved_or_failed"]
    assert not report["samples"][-1]["unresolved_or_failed"]
    assert not report["sampled_path_clear"]
    assert any(r["status"] == "FAIL" for s in report["samples"] for r in s["unresolved_or_failed"])
    clear = sample_translation(
        {"part": part}, {"obstacle": obstacle.translate((0, 5, 0))}, (10, 0, 0)
    )
    assert clear["sampled_path_clear"]
    assert clear["continuously_separated_by_swept_aabb"] == [["part", "obstacle"]]
    with pytest.raises(ValueError):
        sample_translation({"part": part}, {"obstacle": obstacle}, (10, 0, 0), step_mm=0)
