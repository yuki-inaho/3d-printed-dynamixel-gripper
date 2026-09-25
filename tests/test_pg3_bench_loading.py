import json
from pathlib import Path

import cadquery as cq
import pytest

from gripper_design.pg3_bench_support import to_world
from scripts.review_pg3 import inspect_pairs
from scripts.review_pg3_bench_loading import loading_stages, validate_stages
from scripts.review_pg3_bench_support import linkage
from scripts.review_pg3_mechanism_insertion import review_stage
from scripts.step_cache import read_rows


@pytest.fixture(scope="module")
def fixture():
    shapes = {
        r.name: r.world
        for r in read_rows("outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step")
    }
    root = Path("outputs/pg3-bench-support-r1")
    report = json.loads((root / "review.json").read_text())
    local = cq.importers.importStep(str(root / "bench_support_CANDIDATE.step")).val()
    return shapes, to_world(local, report["frame"])


def test_loading_has_complete_incremental_inventory(fixture):
    shapes, support = fixture
    stages = loading_stages(shapes, support)
    expected, _ = linkage(shapes)
    installed = {"JIG": support}
    assert len(stages) == 17
    assert sum(len(s["obstacles"]) for s in stages) == 153
    for stage in stages:
        assert len(stage["movers"]) == 1
        assert set(stage["obstacles"]) == set(installed)
        assert all(s is installed[n] for n, s in stage["obstacles"].items())
        assert all(s is shapes[n] for n, s in stage["movers"].items())
        assert not set(installed) & set(stage["movers"])
        installed.update(stage["movers"])
        assert set(stage["not_yet_installed"]) == set(expected) - set(installed)
    assert set(installed) == {"JIG", *expected}


def test_missing_final_washer_is_rejected(fixture):
    shapes, support = fixture
    with pytest.raises((KeyError, ValueError)):
        loading_stages(
            {n: s for n, s in shapes.items() if n != "PG3_pivot_drive_R_washer"}, support
        )


def test_previously_loaded_material_cannot_be_omitted(fixture):
    shapes, support = fixture
    stages = loading_stages(shapes, support)
    del stages[-1]["obstacles"]["PG3_link_R"]
    with pytest.raises(ValueError, match="already installed"):
        validate_stages(stages, linkage(shapes)[0], support)


def test_previously_loaded_material_cannot_be_relocated(fixture):
    shapes, support = fixture
    stages = loading_stages(shapes, support)
    stages[-1]["obstacles"]["PG3_link_R"] = shapes["PG3_link_R"].translate((0, 10, 0))
    with pytest.raises(ValueError, match="already installed"):
        validate_stages(stages, linkage(shapes)[0], support)


def test_nut_loading_direction_is_not_always_clear(fixture):
    shapes, support = fixture
    nut = shapes["PG3_pivot_drive_R_nut"]
    forward = review_stage({"nut": nut}, {"JIG": support}, (60, 0, 0))
    backward = review_stage({"nut": nut}, {"JIG": support}, (-6, 0, 0))
    assert forward["continuous_translation_volume_clear"]
    assert not backward["continuous_translation_volume_clear"]
    assert backward["actual_penetration_samples"]
    sample = inspect_pairs({"nut": nut.translate((-3, 0, 0)), "JIG": support}, [("nut", "JIG")])
    assert sample["counts"] == {"FAIL": 1}
    assert sample["pairs"][0]["volume_mm3"] > 1


def test_host_loading_supplement_keeps_complete_pair_coverage(fixture):
    from scripts.review_pg3_bench_loading import supplement_stage

    shapes, support = fixture
    stage = loading_stages(shapes, support)[4]
    raw = review_stage(stage["movers"], stage["obstacles"], (60, 0, 0))
    result = supplement_stage(stage, raw)
    assert not raw["continuous_translation_volume_clear"]
    assert result["nominal_material_path_clear"]
    assert len(result["selected_pair_upper_bounds_mm3"]) == len(stage["obstacles"])
    assert len(result["inverse_nut_paths"]) == 2
    assert not result["physical_retention_proven"]


def test_supplement_does_not_accept_missing_pair_coverage(fixture):
    from scripts.review_pg3_bench_loading import supplement_stage

    shapes, support = fixture
    stage = loading_stages(shapes, support)[0]
    with pytest.raises(ValueError, match="coverage"):
        supplement_stage(
            stage, {"far_pairs": [], "near_pairs": [], "actual_penetration_samples": []}
        )


def test_supplement_retains_penetration_veto_and_rejects_other_paths(fixture):
    from scripts.review_pg3_bench_loading import supplement_stage

    shapes, support = fixture
    stage = loading_stages(shapes, support)[0]
    raw = review_stage(stage["movers"], stage["obstacles"], (60, 0, 0))
    assert supplement_stage(stage, raw)["nominal_material_path_clear"]
    # Inject a contradictory evaluator finding to ensure a small bound cannot
    # override a reported material collision.
    raw["actual_penetration_samples"] = [{"status": "FAIL", "volume_mm3": 1.0}]
    assert not supplement_stage(stage, raw)["nominal_material_path_clear"]
    raw["start_offset_mm"] = [-60, 0, 0]
    with pytest.raises(ValueError, match="source .X60mm"):
        supplement_stage(stage, raw)
