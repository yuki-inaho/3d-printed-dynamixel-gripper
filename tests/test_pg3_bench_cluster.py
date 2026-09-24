import pytest

from scripts.assembly_io import read_step
from scripts.review_pg3 import inspect_pairs
from scripts.review_pg3_bench_cluster import bench_cluster
from scripts.review_pg3_mechanism_insertion import review_stage
from scripts.verify_pg3_service_stages import mechanism_stages


@pytest.fixture(scope="module")
def shapes():
    return {
        r.name: r.world
        for r in read_step("outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step")[2]
    }


def test_complete_bench_cluster_and_final_horn_access(shapes):
    result = bench_cluster(shapes)
    assert set(result) == {
        "movers",
        "obstacles",
        "horn_bolts",
        "installed",
        "bench_tools",
        "horn_tools",
    }
    expected = {"PG3_crank", "PG3_horn_spacer"}
    for side in ("R", "L"):
        expected.update({f"PG3_carriage_{side}", f"PG3_link_{side}"})
        expected.update(
            f"PG3_pivot_{kind}_{side}_{part}"
            for kind in ("drive", "carriage")
            for part in ("bolt", "washer", "nut")
        )
    assert set(result["movers"]) == expected
    assert len(result["movers"]) == 18 and len(result["obstacles"]) == 240
    assert not set(result["movers"]) & set(result["obstacles"])
    assert {n for n in shapes if n.startswith("ARM_")} <= set(result["obstacles"])
    assert len(result["horn_bolts"]) == 4
    assert len(result["bench_tools"]) == len(result["horn_tools"]) == 8
    assert len(result["installed"]) == 262
    for collection in ("movers", "obstacles", "horn_bolts", "installed"):
        assert all(s is shapes[n] for n, s in result[collection].items())
    assert not any(n.startswith("PG3_finger_") for n in result["installed"])


def test_missing_frame_cannot_make_cluster_insertion_clear(shapes, monkeypatch):
    canonical = mechanism_stages(shapes, horn_l_key=True)
    del canonical["G1_frame_case"][0]["PG3_frame"]
    monkeypatch.setattr(
        "scripts.review_pg3_bench_cluster.mechanism_stages", lambda *a, **kw: canonical
    )
    with pytest.raises(ValueError, match="complete G1"):
        bench_cluster(shapes)


def test_relocated_link_is_not_an_equivalent_bench_cluster(shapes, monkeypatch):
    canonical = mechanism_stages(shapes, horn_l_key=True)
    canonical["G4_link_pivots"][0]["PG3_link_R"] = shapes["PG3_link_R"].translate((10, 0, 0))
    monkeypatch.setattr(
        "scripts.review_pg3_bench_cluster.mechanism_stages", lambda *a, **kw: canonical
    )
    with pytest.raises(ValueError, match="saved linkage"):
        bench_cluster(shapes)


def test_omitting_last_screw_withdrawal_is_rejected(shapes, monkeypatch):
    canonical = mechanism_stages(shapes, horn_l_key=True)
    del canonical["G2_horn_drive"][1]["WITHDRAWAL_PG3_horn_bolt_0"]
    monkeypatch.setattr(
        "scripts.review_pg3_bench_cluster.mechanism_stages", lambda *a, **kw: canonical
    )
    with pytest.raises(ValueError, match="every final screw"):
        bench_cluster(shapes)


@pytest.mark.parametrize("side", ["R", "L"])
def test_wrong_side_approach_hits_frame_instead_of_passing(shapes, side):
    carriage, frame = shapes[f"PG3_carriage_{side}"], shapes["PG3_frame"]
    forward = review_stage({"carriage": carriage}, {"frame": frame}, (60, 0, 0))
    backward = review_stage({"carriage": carriage}, {"frame": frame}, (-60, 0, 0))
    assert forward["continuous_translation_volume_clear"]
    assert not backward["continuous_translation_volume_clear"]
    sample = inspect_pairs(
        {"carriage": carriage.translate((-0.5, 0, 0)), "frame": frame}, [("carriage", "frame")]
    )
    assert sample["pairs"][0]["status"] == "FAIL"
    assert sample["pairs"][0]["volume_mm3"] > 0.1
