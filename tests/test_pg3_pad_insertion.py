import cadquery as cq
import pytest

from scripts.assembly_io import bounds
from scripts.review_pg3_pad_insertion import pad_stages, review_path
from scripts.step_cache import read_rows
from scripts.verify_pg3_service_stages import mechanism_stages


@pytest.fixture(scope="module")
def shapes():
    return {
        r.name: r.world
        for r in read_rows("outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step")
    }


def test_saved_pad_stages_keep_complete_previous_assembly(shapes):
    stages = pad_stages(shapes)
    assert list(stages) == ["G7_R_pad", "G7_L_pad"]
    previous = mechanism_stages(shapes, horn_l_key=True)["G6_fingers"][0]
    assert len(previous) == 286
    for side, (movers, obstacles, waypoints) in zip(("R", "L"), stages.values(), strict=True):
        assert set(movers) == {f"PG3_pad_{side}"}
        assert set(previous) == set(obstacles)
        assert all(obstacles[n] is previous[n] for n in previous)
        assert len(waypoints) == 3
        assert waypoints[-1] == (0, 0, 0)
        previous = obstacles | movers
    assert len(previous) == 288
    assert set(previous) == {n for n in shapes if not n.startswith("CAMERA_")}


def test_pad_approach_is_inside_gap_without_sliding_on_bond_face(shapes):
    stages = pad_stages(shapes)
    for side in ("R", "L"):
        mover, _, waypoints = stages[f"G7_{side}_pad"]
        sign = 1 if side == "R" else -1
        assert waypoints == [(60, 0, sign * 3), (0, 0, sign * 3), (0, 0, 0)]
        pad = bounds(mover[f"PG3_pad_{side}"])
        assert [pad[i + 3] - pad[i] for i in range(3)] == pytest.approx([20, 28, 1])
        intermediate = bounds(mover[f"PG3_pad_{side}"].translate(waypoints[1]))
        assert bounds(shapes["PG3_finger_R"])[5] < intermediate[2]
        assert intermediate[5] < bounds(shapes["PG3_finger_L"])[2]


def test_segment_uses_end_placed_geometry_and_relative_offset(monkeypatch):
    cube = cq.Solid.makeBox(1, 1, 1)
    calls = []

    def spy(movers, obstacles, offset):
        calls.append((bounds(movers["pad"]), obstacles, offset))
        return {"continuous_translation_volume_clear": True}

    monkeypatch.setattr("scripts.review_pg3_pad_insertion.review_stage", spy)
    obstacles = {"wall": cube.translate((0, 20, 0))}
    result = review_path({"pad": cube}, obstacles, [(60, 0, 3), (0, 0, 3), (0, 0, 0)])
    assert len(result["segments"]) == len(calls) == 2
    assert calls[0][0] == pytest.approx([0, 0, 3, 1, 1, 4])
    assert calls[1][0] == pytest.approx([0, 0, 0, 1, 1, 1])
    assert calls[0][2] == (60, 0, 0)
    assert calls[1][2] == (0, 0, 3)
    assert all(call[1] is obstacles for call in calls)
    assert (
        result["segments"][0]["end_offset_from_saved_mm"]
        == result["segments"][1]["start_offset_from_saved_mm"]
    )
    assert result["continuous_path_volume_clear"]


@pytest.mark.parametrize(
    "points",
    [
        [],
        [(0, 0, 0)],
        [(1, 0, 0), (0, 0, 1)],
        [(float("nan"), 0, 0), (0, 0, 0)],
        [(1, 0), (0, 0, 0)],
        [(0, 0, 0), (0, 0, 0)],
    ],
)
def test_invalid_route_not_vacuously_accepted(points):
    with pytest.raises(ValueError):
        review_path({"pad": cq.Solid.makeBox(1, 1, 1)}, {}, points)


def test_removed_prior_part_is_rejected(shapes, monkeypatch):
    tools = mechanism_stages(shapes, horn_l_key=True)
    del tools["G6_fingers"][0]["PG3_finger_R_14_bolt"]
    monkeypatch.setattr("scripts.review_pg3_pad_insertion.mechanism_stages", lambda *a, **kw: tools)
    with pytest.raises(ValueError, match="final pad stage"):
        pad_stages(shapes)


def test_changed_prior_geometry_is_rejected(shapes, monkeypatch):
    tools = mechanism_stages(shapes, horn_l_key=True)
    tools["G6_fingers"][0]["PG3_finger_L"] = shapes["PG3_finger_L"].translate((0, 0, 1))
    monkeypatch.setattr("scripts.review_pg3_pad_insertion.mechanism_stages", lambda *a, **kw: tools)
    with pytest.raises(ValueError, match="final pad stage"):
        pad_stages(shapes)


def test_straight_normal_approach_crosses_opposite_saved_finger(shapes):
    result = review_path(
        {"pad": shapes["PG3_pad_R"]},
        {"opposite": shapes["PG3_finger_L"]},
        [(0, 0, 60), (0, 0, 0)],
    )
    assert not result["continuous_path_volume_clear"]
    displaced = shapes["PG3_pad_R"].translate((0, 0, 18))
    assert displaced.intersect(shapes["PG3_finger_L"]).Volume() > 100
