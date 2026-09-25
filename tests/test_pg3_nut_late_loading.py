import pytest

from scripts.assembly_io import bounds
from scripts.review_pg3 import inspect_pairs
from scripts.review_pg3_nut_late_loading import fastening_envelopes, late_stages
from scripts.review_pg3_slider_link_insertion import later_stages
from scripts.step_cache import read_rows
from scripts.verify_pg3_service_stages import mechanism_stages


@pytest.fixture(scope="module")
def shapes():
    return {
        r.name: r.world
        for r in read_rows("outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step")
    }


def test_twelve_late_stages_retain_installed_arm_motor_and_every_previous_nut(shapes):
    stages = late_stages(shapes)
    assert len(stages) == 12
    previous = {
        n: s
        for n, s in shapes.items()
        if n.startswith("ARM_") or n in {"PG3_XL430_fixed", "PG3_XL430_horn"}
    }
    counts = []
    final = {}
    for movers, obstacles, group in stages.values():
        assert set(previous) <= set(obstacles)
        assert all(obstacles[n] is previous[n] for n in previous)
        assert len(movers) == 1 and not set(movers) & set(obstacles)
        assert all(obstacles[n] is shapes[n] for n in obstacles)
        counts.append(len(obstacles))
        previous = obstacles | movers
        final[group] = previous
    assert counts == [236, 237, 238, 239, 246, 247, 249, 250, 251, 253, 254, 255]
    assert {g: len(s) for g, s in final.items()} == {"G1": 240, "G2": 248, "G3_R": 252, "G3_L": 256}
    tools = mechanism_stages(shapes, horn_l_key=True)
    assert set(final["G1"]) == set(tools["G1_frame_case"][0])
    assert set(final["G2"]) == set(tools["G2_horn_drive"][0])
    later = later_stages(shapes)
    for side in ("R", "L"):
        body, obstacles, _ = later[f"G3_{side}"]
        assert set(final[f"G3_{side}"]) == set(body) | set(obstacles)


def test_omitted_arm_cannot_create_clear_late_access(shapes, monkeypatch):
    tools = mechanism_stages(shapes, horn_l_key=True)
    del tools["G1_frame_case"][0]["ARM_P06_PG3_support"]
    monkeypatch.setattr(
        "scripts.review_pg3_nut_late_loading.mechanism_stages", lambda *a, **kw: tools
    )
    with pytest.raises(ValueError, match="prior components"):
        late_stages(shapes)


def test_relocated_motor_cannot_replace_installed_obstacle(shapes, monkeypatch):
    tools = mechanism_stages(shapes, horn_l_key=True)
    tools["G2_horn_drive"][0]["PG3_XL430_fixed"] = shapes["PG3_XL430_fixed"].translate((100, 0, 0))
    monkeypatch.setattr(
        "scripts.review_pg3_nut_late_loading.mechanism_stages", lambda *a, **kw: tools
    )
    with pytest.raises(ValueError, match="saved geometry"):
        late_stages(shapes)


def test_group_nuts_cannot_be_pretended_already_installed(shapes, monkeypatch):
    from scripts.review_pg3_nut_loading import preload_stages

    preload = preload_stages(shapes)
    name = "PG3_pivot_drive_R_nut"
    mover, obstacles, _ = preload[name]
    preload[name] = (mover, obstacles, "G3_R")
    monkeypatch.setattr("scripts.review_pg3_nut_late_loading.preload_stages", lambda *a: preload)
    with pytest.raises(ValueError, match="already installed"):
        late_stages(shapes)


@pytest.mark.parametrize("side", ["R", "L"])
def test_drive_nut_rear_stop_is_not_unrestricted_axial_escape(shapes, side):
    nut = shapes[f"PG3_pivot_drive_{side}_nut"]
    frame = shapes["PG3_frame"]
    at_stop = nut.translate((-1.2, 0, 0))
    clear = inspect_pairs({"nut": at_stop, "frame": frame}, [("nut", "frame")])
    beyond = inspect_pairs({"nut": nut.translate((-1.3, 0, 0)), "frame": frame}, [("nut", "frame")])
    assert clear["pairs"][0]["status"] == "PASS"
    assert clear["pairs"][0]["volume_mm3"] < 1e-4
    assert beyond["pairs"][0]["status"] == "FAIL"
    assert beyond["pairs"][0]["volume_mm3"] == pytest.approx(1.07148138, abs=1e-5)
    # A dimensional observation only: not a certificate against tilt or lateral escape.
    assert bounds(at_stop)[3] - bounds(shapes["PG3_crank"])[0] == pytest.approx(0.6)


def test_fastening_envelope_excludes_only_target_nut_and_target_bolt(shapes):
    rows = fastening_envelopes(shapes)
    assert len(rows) == 12
    complete = {n for n in shapes if not n.startswith("CAMERA_")}
    assert len(complete) == 288
    for name, (movers, obstacles, _) in rows.items():
        assert set(movers) == {name}
        bolt = name.removesuffix("_nut") + "_bolt"
        assert set(obstacles) == complete - {name, bolt}
        assert all(obstacles[n] is shapes[n] for n in obstacles)
        assert len(obstacles) == 286


def test_fastening_context_rejects_unknown_extra_non_camera_part(shapes):
    changed = shapes | {"UNASSIGNED_part": shapes["PG3_frame"]}
    with pytest.raises(ValueError, match="final (?:pre|non)-camera inventory"):
        fastening_envelopes(changed)
