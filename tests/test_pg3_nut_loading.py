import math

import cadquery as cq
import pytest

from scripts.assembly_io import bounds
from scripts.review_pg3_mechanism_insertion import insertion_stages, review_stage
from scripts.review_pg3_nut_loading import (
    hex_translation_enclosure,
    preload_stages,
    review_loaded_nut,
)
from scripts.review_pg3_slider_link_insertion import later_stages
from scripts.step_cache import read_rows


@pytest.fixture(scope="module")
def shapes():
    return {
        r.name: r.world
        for r in read_rows("outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step")
    }


def clusters(shapes):
    first = insertion_stages(shapes)
    later = later_stages(shapes)
    return {
        "G1": first["G1_frame_case"][0],
        "G2": first["G2_horn_drive"][0],
        "G3_R": later["G3_R"][0],
        "G3_L": later["G3_L"][0],
    }


def test_all_twelve_nuts_are_loaded_once_into_the_reviewed_clusters(shapes):
    stages = preload_stages(shapes)
    assert len(stages) == 12
    groups = clusters(shapes)
    previous = {
        g: {n: s for n, s in c.items() if not n.endswith("_nut")} for g, c in groups.items()
    }
    seen = []
    counts = {g: 0 for g in groups}
    for movers, obstacles, group in stages.values():
        assert len(movers) == 1
        assert set(obstacles) == set(previous[group])
        assert all(obstacles[n] is previous[group][n] for n in obstacles)
        assert not set(movers) & set(obstacles)
        previous[group] = obstacles | movers
        seen.extend(movers)
        counts[group] += 1
    assert counts == {"G1": 4, "G2": 2, "G3_R": 3, "G3_L": 3}
    assert len(seen) == len(set(seen))
    assert set(seen) == {n for n in shapes if n.startswith("PG3_") and n.endswith("_nut")}
    for group, final in previous.items():
        assert set(final) == set(groups[group])
        assert all(final[n] is groups[group][n] for n in final)


def test_missing_host_cannot_be_a_free_space_pass(shapes, monkeypatch):
    first = insertion_stages(shapes)
    del first["G2_horn_drive"][0]["PG3_crank"]
    monkeypatch.setattr("scripts.review_pg3_nut_loading.insertion_stages", lambda *a: first)
    with pytest.raises(ValueError, match="host inventory"):
        preload_stages(shapes)


def test_displaced_host_cannot_replace_saved_geometry(shapes, monkeypatch):
    first = insertion_stages(shapes)
    first["G1_frame_case"][0]["PG3_frame"] = shapes["PG3_frame"].translate((10, 0, 0))
    monkeypatch.setattr("scripts.review_pg3_nut_loading.insertion_stages", lambda *a: first)
    with pytest.raises(ValueError, match="saved geometry"):
        preload_stages(shapes)


def test_missing_nut_is_not_silently_out_of_scope(shapes, monkeypatch):
    later = later_stages(shapes)
    del later["G3_R"][0]["PG3_finger_R_14_nut"]
    monkeypatch.setattr("scripts.review_pg3_nut_loading.later_stages", lambda *a: later)
    with pytest.raises(ValueError, match="nut inventory"):
        preload_stages(shapes)


def test_front_loading_hex_nut_is_rejected(shapes):
    result = review_stage(
        {"nut": shapes["PG3_cap_37.5_24.5_nut"]},
        {"host": shapes["PG3_frame"]},
        (30, 0, 0),
    )
    assert not result["continuous_translation_volume_clear"]
    displaced = shapes["PG3_cap_37.5_24.5_nut"].translate((3, 0, 0))
    assert displaced.intersect(shapes["PG3_frame"]).Volume() > 1


def test_hex_enclosure_contains_all_saved_nut_material_over_translation(shapes):
    nut = shapes["PG3_cap_37.5_24.5_nut"]
    cover, proof = hex_translation_enclosure(nut, (-30, 0, 0))
    assert cover.isValid() and len(cover.Solids()) == 1
    assert len(proof["support_halfplanes"]) == 6
    for x in (-30, -15, 0):
        assert nut.translate((x, 0, 0)).cut(cover).Volume() < 1e-5
    bb = bounds(nut)
    cb = bounds(cover)
    assert cb[0] < bb[0] - 30
    assert cb[3] > bb[3]


def test_support_bounds_include_curved_bulge_between_vertices():
    prism = cq.Workplane("YZ").polygon(6, 8 / math.sqrt(3)).extrude(1.6).val()
    sphere = cq.Workplane().sphere(0.3).val().rotate((0, 0, 0), (1, 0, 0), 90)
    source = prism.fuse(sphere.translate((0.8, 0, 2.05)))
    assert bounds(source)[5] > max(v.Z for v in source.Vertices()) + 0.1
    cover, _ = hex_translation_enclosure(source, (-30, 0, 0))
    assert cover.isInside((0.8, 0, 2.349))
    assert cover.isInside((-29.2, 0, 2.349))


def test_hex_bound_rejects_unsupported_shape_or_motion(shapes):
    with pytest.raises(ValueError):
        hex_translation_enclosure(cq.Solid.makeBox(1, 1, 1), (-30, 0, 0))
    nut = shapes["PG3_cap_37.5_24.5_nut"]
    for offset in ((0, 1, 0), (float("nan"), 0, 0), (1, 0)):
        with pytest.raises(ValueError):
            hex_translation_enclosure(nut, offset)


@pytest.mark.parametrize(
    "nut_name,host_name",
    [
        ("PG3_cap_37.5_24.5_nut", "PG3_frame"),
        ("PG3_pivot_drive_R_nut", "PG3_crank"),
        ("PG3_pivot_carriage_R_nut", "PG3_carriage_R"),
        ("PG3_finger_R_-14_nut", "PG3_carriage_R"),
    ],
)
def test_tight_saved_nut_path_and_seat_intrusion_control(shapes, nut_name, host_name):
    nut = shapes[nut_name]
    host = {"host": shapes[host_name]}
    good = review_loaded_nut({"nut": nut}, host)
    assert good["supplemented_continuous_translation_volume_clear"]
    assert not good["continuous_translation_volume_clear"]
    bad = review_loaded_nut({"nut": nut.translate((0.2, 0, 0))}, host)
    assert not bad["supplemented_continuous_translation_volume_clear"]
    assert any(
        bad["hex_enclosure"][method]["pairs"][0]["status"] == "FAIL"
        for method in ("world", "common_reexpression_mid90")
    )
