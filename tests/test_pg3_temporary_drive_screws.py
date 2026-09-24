import math

import cadquery as cq
import pytest

from scripts.assembly_io import bounds, read_step
from scripts.review_pg3 import inspect_pairs
from scripts.review_pg3_mechanism_insertion import review_stage
from scripts.review_pg3_pivot_stacks import pick, profiles
from scripts.review_pg3_slider_link_insertion import later_stages
from scripts.review_pg3_temporary_drive_screws import candidate


@pytest.fixture(scope="module")
def shapes():
    return {
        r.name: r.world
        for r in read_step("outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step")[2]
    }


def test_existing_screws_seat_without_washers_and_remain_in_later_stages(shapes):
    result = candidate(shapes)
    assert set(result) == {"temporary_screws", "stacks", "stages"}
    names = {f"PG3_pivot_drive_{s}_bolt" for s in ("R", "L")}
    assert set(result["temporary_screws"]) == names
    assert list(result["stages"]) == ["G2", "G3_R", "G3_L", "G4_R_link", "G4_L_link"]
    counts = []
    for i, (movers, obstacles, _) in enumerate(result["stages"].values()):
        counts.append((len(movers), len(obstacles)))
        placed = movers if i == 0 else obstacles
        assert names <= set(placed)
        assert all(placed[n] is result["temporary_screws"][n] for n in names)
        assert not set(movers) & set(obstacles)
        assert {n for n in shapes if n.startswith("ARM_")} <= set(obstacles)
        for n, s in (movers | obstacles).items():
            assert s is (result["temporary_screws"][n] if n in names else shapes[n])
    assert counts == [(6, 240), (4, 250), (4, 254), (1, 258), (1, 259)]
    for row in result["stacks"].values():
        assert row["translation_mm"] == pytest.approx([-0.5, 0, 0])
        assert row["head_seat"]["pass_contact"]
        assert row["head_seat"]["common_area_mm2"] == pytest.approx(math.pi * (1.9**2 - 1.15**2))
        assert row["nominal_nut_span_overlap_mm"] == pytest.approx(1.6)
        assert row["tip_x_mm"] == pytest.approx(19.6)
        assert row["head_to_link_radial_gap_mm"] == pytest.approx(0.8)
        assert not row["actual_thread_engagement_verified"]


def test_no_carriage_nut_can_disappear_to_manufacture_an_easier_path(shapes, monkeypatch):
    stages = later_stages(shapes)
    del stages["G3_R"][0]["PG3_pivot_carriage_R_nut"]
    monkeypatch.setattr("scripts.review_pg3_temporary_drive_screws.later_stages", lambda *a: stages)
    with pytest.raises(ValueError, match="inventory"):
        candidate(shapes)


def test_carriage_geometry_cannot_be_relocated_to_make_room(shapes, monkeypatch):
    stages = later_stages(shapes)
    stages["G3_R"][0]["PG3_carriage_R"] = shapes["PG3_carriage_R"].translate((100, 0, 0))
    monkeypatch.setattr("scripts.review_pg3_temporary_drive_screws.later_stages", lambda *a: stages)
    with pytest.raises(ValueError, match="saved shapes"):
        candidate(shapes)


@pytest.mark.parametrize("side", ["R", "L"])
def test_longer_temporary_tip_is_detected_as_real_frame_penetration(shapes, side):
    name = f"PG3_pivot_drive_{side}_bolt"
    screw = candidate(shapes)["temporary_screws"][name]
    shank = pick(profiles(screw), 1, "convex")
    tip = shank["span_x_mm"][0]
    extension = cq.Solid.makeCylinder(1, 0.6, (tip - 0.5, *shank["axis_yz_mm"]), (1, 0, 0))
    bad = screw.fuse(extension)
    assert bad.isValid() and len(bad.Solids()) == 1
    assert bounds(bad)[0] == pytest.approx(tip - 0.5)
    frame = shapes["PG3_frame"]
    normal = inspect_pairs({"screw": screw, "frame": frame}, [("screw", "frame")])["pairs"][0]
    negative = inspect_pairs({"screw": bad, "frame": frame}, [("screw", "frame")])["pairs"][0]
    assert normal["status"] == "PASS"
    assert negative["status"] == "FAIL" and negative["volume_mm3"] > 0.1


@pytest.mark.parametrize("side", ["R", "L"])
def test_existing_small_head_clears_link_but_washer_sized_head_blocks_path(shapes, side):
    prefix = f"PG3_pivot_drive_{side}"
    prepared = candidate(shapes)
    screw = prepared["temporary_screws"][f"{prefix}_bolt"]
    washer = shapes[f"{prefix}_washer"].translate((-0.5, 0, 0))
    enlarged = screw.fuse(washer)
    assert enlarged.isValid() and len(enlarged.Solids()) == 1
    link = shapes[f"PG3_link_{side}"]
    clear = review_stage({"link": link}, {"screw": screw}, (60, 0, 0))
    blocked = review_stage({"link": link}, {"screw": enlarged}, (60, 0, 0))
    assert clear["continuous_translation_volume_clear"]
    assert not blocked["continuous_translation_volume_clear"]
    # A targeted sample catches the narrow axial obstruction missed by coarse samples.
    sample = inspect_pairs(
        {"link": link.translate((2, 0, 0)), "screw": enlarged}, [("link", "screw")]
    )
    assert sample["pairs"][0]["status"] == "FAIL"
    assert sample["pairs"][0]["volume_mm3"] > 0.1
