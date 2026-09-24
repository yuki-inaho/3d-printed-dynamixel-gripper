from types import SimpleNamespace

import cadquery as cq
import numpy as np
import pytest
import trimesh

from gripper_design.pg3 import to_arm
from simulation.pg3_scene import write_scene


def test_scene_uses_installed_geometry_not_stale_neutral(tmp_path):
    stale = cq.Solid.makeBox(1, 2, 3)
    updated = cq.Solid.makeBox(4, 5, 6, (10, 20, 30))
    pg3 = SimpleNamespace(neutral={"frame": stale})
    whole = {
        "PG3_frame": to_arm(updated),
        "CAMERA_REFERENCE_UNCONFIRMED": cq.Solid.makeBox(2, 3, 4),
    }
    write_scene(pg3, tmp_path / "scene", assembly_factory=lambda m, a: whole)
    mesh = trimesh.load_mesh(tmp_path / "scene/meshes/PG3_frame.obj", process=False)
    np.testing.assert_allclose(mesh.bounds, [[0.01, 0.02, 0.03], [0.014, 0.025, 0.036]])


@pytest.mark.parametrize("missing", (True, False))
def test_scene_rejects_missing_or_unmodelled_pg3_occurrence(tmp_path, missing):
    box = cq.Solid.makeBox(1, 2, 3)
    pg3 = SimpleNamespace(neutral={"frame": box})
    whole = {"CAMERA_REFERENCE_UNCONFIRMED": box}
    if not missing:
        whole.update(PG3_frame=to_arm(box), PG3_unmodelled=to_arm(box))
    with pytest.raises(ValueError, match="PG3 occurrence inventory"):
        write_scene(pg3, tmp_path / "scene", assembly_factory=lambda m, a: whole)
