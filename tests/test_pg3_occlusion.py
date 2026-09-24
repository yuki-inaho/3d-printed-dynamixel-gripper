import numpy as np

from scripts.review_pg3_occlusion import visibility
from simulation.pg3_scene import mujoco


def test_visible_partial_and_hidden_controls_preserve_scene_groups():
    model = mujoco.MjModel.from_xml_string("""<mujoco>
      <visual><quality offsamples="0"/></visual><worldbody>
        <camera name="camera_proxy" pos="0 0 3"/>
        <geom name="target" type="box" size=".3 .3 .1" pos="0 0 0"/>
        <geom name="obstacle" type="box" size=".4 .4 .1" pos="10 0 1"/>
      </worldbody></mujoco>""")
    data = mujoco.MjData(model)
    groups = model.geom_group.copy()
    renderer = mujoco.Renderer(model, 120, 160)
    results = []
    try:
        for x in (10, 0.45, 0):
            model.geom_pos[model.geom("obstacle").id, 0] = x
            mujoco.mj_forward(model, data)
            results.append(visibility(renderer, model, data, "target"))
            assert np.array_equal(model.geom_group, groups)
    finally:
        renderer.close()
    assert results[0]["visible_fraction"] == 1
    assert 0 < results[1]["visible_fraction"] < 1
    assert results[2]["visible_fraction"] == 0
    assert len({r["unobstructed_silhouette_pixels"] for r in results}) == 1
