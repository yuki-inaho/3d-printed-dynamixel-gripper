import numpy as np
import pytest

from scripts.review_pg3_occluders import attribute_pixels


def test_exact_visible_and_occluder_counts():
    ref = np.array([[True, True, True], [True, False, False]])
    seg = np.array([[[1, 5], [2, 5], [2, 5]], [[3, 5], [-1, -1], [-1, -1]]])
    result = attribute_pixels(ref, seg, 1, {1: "pad", 2: "finger", 3: "frame"}, 5)
    assert result["reference_pixels"] == 4
    assert result["visible_pixels"] == 1
    assert result["visible_fraction"] == 0.25
    assert result["occluded_pixels"] == 3
    assert result["unclassified_pixels"] == 0
    assert {r["name"]: r["pixels"] for r in result["occluders"]} == {"finger": 2, "frame": 1}


def test_unclassified_background_and_unknown_ids_are_not_a_part():
    ref = np.ones((1, 4), dtype=bool)
    seg = np.array([[[1, 5], [-1, -1], [9, 5], [2, 1]]])
    result = attribute_pixels(ref, seg, 1, {1: "pad", 2: "finger"}, 5)
    assert result["unclassified_pixels"] == 3
    assert result["occluded_pixels"] == 0
    assert result["occluders"] == []
    assert result["visible_pixels"] == 1


def test_target_outside_reference_is_rejected():
    with pytest.raises(ValueError, match="outside reference"):
        attribute_pixels(np.zeros((1, 1), dtype=bool), np.array([[[1, 5]]]), 1, {1: "pad"}, 5)


def test_empty_reference_is_not_full_visibility():
    result = attribute_pixels(
        np.zeros((1, 1), dtype=bool), np.array([[[-1, -1]]]), 1, {1: "pad"}, 5
    )
    assert result["visible_fraction"] is None
    assert result["reference_pixels"] == 0


@pytest.mark.parametrize("seg", [np.zeros((1, 1, 2), dtype=float), np.zeros((2, 1, 2), dtype=int)])
def test_bad_segmentation_rejected(seg):
    with pytest.raises(ValueError):
        attribute_pixels(np.ones((1, 1), dtype=bool), seg, 1, {1: "pad"}, 5)


@pytest.mark.parametrize("x,expected", [(10, "visible"), (0.45, "partial"), (0, "hidden")])
def test_renderer_attributes_known_obstacle_and_restores_groups(x, expected):
    from scripts.review_pg3_occluders import masks
    from simulation.pg3_scene import mujoco

    model = mujoco.MjModel.from_xml_string("""<mujoco>
      <visual><quality offsamples="0"/></visual><worldbody>
        <camera name="camera_proxy" pos="0 0 3"/>
        <geom name="pad" type="box" size=".3 .3 .1" pos="0 0 0"/>
        <geom name="blocker" type="box" size=".4 .4 .1" pos="0 0 1"/>
      </worldbody></mujoco>""")
    model.geom_pos[model.geom("blocker").id, 0] = x
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    groups = model.geom_group.copy()
    renderer = mujoco.Renderer(model, 120, 160)
    try:
        gid = model.geom("pad").id
        ref, actual = masks(renderer, model, data, gid)
        result = attribute_pixels(
            ref,
            actual,
            gid,
            {i: model.geom(i).name for i in range(model.ngeom)},
            int(mujoco.mjtObj.mjOBJ_GEOM),
        )
    finally:
        renderer.close()
    assert np.array_equal(model.geom_group, groups)
    assert result["unclassified_pixels"] == 0
    if expected == "visible":
        assert result["visible_fraction"] == 1 and result["occluders"] == []
    else:
        assert [r["name"] for r in result["occluders"]] == ["blocker"]
        if expected == "partial":
            assert 0 < result["visible_fraction"] < 1
        else:
            assert result["visible_fraction"] == 0
