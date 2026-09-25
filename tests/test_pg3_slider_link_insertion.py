import pytest

from scripts.review_pg3_slider_link_insertion import later_stages
from scripts.step_cache import read_rows
from scripts.verify_pg3_service_stages import mechanism_stages


@pytest.fixture(scope="module")
def shapes():
    return {
        r.name: r.world
        for r in read_rows("outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step")
    }


def test_saved_assembly_requires_all_six_ordered_stages(shapes):
    stages = later_stages(shapes)
    assert list(stages) == [
        "G3_R",
        "G3_L",
        "G4_R_link",
        "G4_R_washers",
        "G4_L_link",
        "G4_L_washers",
    ]


def test_existing_parts_and_right_retention_remain_for_left_insertion(shapes):
    stages = later_stages(shapes)
    previous = mechanism_stages(shapes, horn_l_key=True)["G2_horn_drive"][0]
    assert len(previous) == 248
    for movers, obstacles, later in stages.values():
        assert set(obstacles) == set(previous)
        assert all(obstacles[n] is previous[n] for n in previous)
        assert not set(movers) & set(obstacles)
        assert not later & (set(movers) | set(obstacles))
        previous = obstacles | movers | {n: shapes[n] for n in later}
        assert not any(n.startswith(("PG3_cap_U", "PG3_cap_D", "CAMERA_")) for n in previous)
    assert len(previous) == 266
    left_obstacles = stages["G4_L_link"][1]
    assert {
        "PG3_link_R",
        "PG3_pivot_drive_R_bolt",
        "PG3_pivot_carriage_R_bolt",
        "PG3_pivot_drive_R_washer",
        "PG3_pivot_carriage_R_washer",
    } <= set(left_obstacles)
    for side in ("R", "L"):
        assert len(stages[f"G3_{side}"][0]) == 4
        assert len(stages[f"G4_{side}_link"][0]) == 1
        assert len(stages[f"G4_{side}_washers"][0]) == 2
        assert len(stages[f"G4_{side}_washers"][2]) == 2


def test_missing_prior_obstacle_not_silently_dropped(shapes, monkeypatch):
    stages = mechanism_stages(shapes, horn_l_key=True)
    del stages["G2_horn_drive"][0]["ARM_P06_PG3_support"]
    monkeypatch.setattr(
        "scripts.review_pg3_slider_link_insertion.mechanism_stages", lambda *a, **kw: stages
    )
    with pytest.raises(ValueError, match="final body stage"):
        later_stages(shapes)


def test_premature_carriage_installation_is_not_an_exclusion(shapes, monkeypatch):
    stages = mechanism_stages(shapes, horn_l_key=True)
    stages["G2_horn_drive"][0]["PG3_carriage_R"] = shapes["PG3_carriage_R"]
    monkeypatch.setattr(
        "scripts.review_pg3_slider_link_insertion.mechanism_stages", lambda *a, **kw: stages
    )
    with pytest.raises(ValueError, match="previously installed"):
        later_stages(shapes)


def test_same_count_different_geometry_cannot_match_final_stage(shapes, monkeypatch):
    stages = mechanism_stages(shapes, horn_l_key=True)
    stages["G4_link_pivots"][0]["PG3_link_R"] = shapes["PG3_link_R"].translate((0.5, 0, 0))
    monkeypatch.setattr(
        "scripts.review_pg3_slider_link_insertion.mechanism_stages", lambda *a, **kw: stages
    )
    with pytest.raises(ValueError, match="final body stage"):
        later_stages(shapes)
