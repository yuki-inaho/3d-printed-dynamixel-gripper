import pytest

from scripts.assembly_io import bounds
from scripts.review_pg3_cap_finger_insertion import finishing_stages
from scripts.review_pg3_mechanism_insertion import review_stage
from scripts.step_cache import read_rows
from scripts.verify_pg3_service_stages import mechanism_stages


@pytest.fixture(scope="module")
def shapes():
    return {
        r.name: r.world
        for r in read_rows("outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step")
    }


def test_saved_assembly_requires_eight_ordered_finishing_stages(shapes):
    assert list(finishing_stages(shapes)) == [
        "G5_U_cap",
        "G5_U_washers",
        "G5_D_cap",
        "G5_D_washers",
        "G6_R_finger",
        "G6_R_washers",
        "G6_L_finger",
        "G6_L_washers",
    ]


def test_every_preceding_part_remains_an_obstacle(shapes):
    previous = mechanism_stages(shapes, horn_l_key=True)["G4_link_pivots"][0]
    assert len(previous) == 266
    stages = finishing_stages(shapes)
    for name, (movers, obstacles, later) in stages.items():
        assert set(obstacles) == set(previous)
        assert all(obstacles[n] is previous[n] for n in previous)
        assert not set(movers) & set(obstacles)
        assert not later & (set(movers) | set(obstacles))
        if name.endswith("washers"):
            assert len(movers) == len(later) == 2
            assert {n.removesuffix("_washer") for n in movers} == {
                n.removesuffix("_bolt") for n in later
            }
        else:
            assert len(movers) == 1
            assert not later
        previous = obstacles | movers | {n: shapes[n] for n in later}
        assert not any(n.startswith(("PG3_pad_", "CAMERA_")) for n in previous)
    assert len(previous) == 286
    assert "PG3_cap_U" in stages["G5_D_cap"][1]
    assert "PG3_finger_R_14_bolt" in stages["G6_L_finger"][1]


def test_cap_hardware_is_on_its_own_saved_cap_side(shapes):
    stages = finishing_stages(shapes)
    for side in ("U", "D"):
        cap = bounds(shapes[f"PG3_cap_{side}"])
        for name in stages[f"G5_{side}_washers"][0]:
            washer = bounds(shapes[name])
            centre_y = (washer[1] + washer[4]) / 2
            assert cap[1] < centre_y < cap[4]


def test_missing_prior_obstacle_is_rejected(shapes, monkeypatch):
    stages = mechanism_stages(shapes, horn_l_key=True)
    del stages["G4_link_pivots"][0]["PG3_link_R"]
    monkeypatch.setattr(
        "scripts.review_pg3_cap_finger_insertion.mechanism_stages", lambda *a, **kw: stages
    )
    with pytest.raises(ValueError, match="final body stage"):
        finishing_stages(shapes)


def test_premature_cap_is_not_omitted_from_collision_checks(shapes, monkeypatch):
    stages = mechanism_stages(shapes, horn_l_key=True)
    stages["G4_link_pivots"][0]["PG3_cap_U"] = shapes["PG3_cap_U"]
    monkeypatch.setattr(
        "scripts.review_pg3_cap_finger_insertion.mechanism_stages", lambda *a, **kw: stages
    )
    with pytest.raises(ValueError, match="previously installed"):
        finishing_stages(shapes)


def test_final_inventory_geometry_must_match_tool_stage(shapes, monkeypatch):
    stages = mechanism_stages(shapes, horn_l_key=True)
    stages["G6_fingers"][0]["PG3_finger_R"] = shapes["PG3_finger_R"].translate((0.5, 0, 0))
    monkeypatch.setattr(
        "scripts.review_pg3_cap_finger_insertion.mechanism_stages", lambda *a, **kw: stages
    )
    with pytest.raises(ValueError, match="final body stage"):
        finishing_stages(shapes)


def test_saved_cap_half_mm_into_frame_is_not_approved(shapes):
    result = review_stage(
        {"cap": shapes["PG3_cap_U"].translate((-0.5, 0, 0))},
        {"frame": shapes["PG3_frame"]},
        (60, 0, 0),
    )
    assert not result["continuous_translation_volume_clear"]
    assert result["summed_overlap_upper_bound_mm3"] > 1e-4
    assert any(
        p["fraction"] == 0 and p["pair"]["volume_mm3"] > 1
        for p in result["actual_penetration_samples"]
    )
