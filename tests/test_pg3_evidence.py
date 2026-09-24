from pathlib import Path

import pytest

from scripts.review_pg3_camera_range import mesh_assets
from scripts.verify_pg3_service_stages import camera_stages


def camera_inventory():
    names = ["camera_carrier", "camera_spacer", "REFERENCE_UNCONFIRMED", "saddle", "front_jaw"]
    names += [f"HW_{kind}_{i}_ENVELOPE" for i in range(4) for kind in ("M2x10", "M2nut")]
    names += [
        f"HW_{kind}_{i}_ENVELOPE"
        for i in range(2)
        for kind in ("M2x10_carrier", "M2nut_carrier", "M3x16", "M3nut")
    ]
    return {f"CAMERA_{name}": object() for name in names}


def test_camera_stages_preserve_required_parts_and_tools():
    shapes = camera_inventory()
    stages = camera_stages(shapes)
    assert [(len(parts), len(tools)) for parts, tools in stages.values()] == [
        (13, 8),
        (16, 2),
        (21, 4),
    ]
    first, second, third = [parts for parts, _ in stages.values()]
    assert set(first) < set(second) < set(third)
    assert "CAMERA_HW_M2nut_carrier_0_ENVELOPE" in first
    for name in shapes:
        bad = {n: v for n, v in shapes.items() if n != name}
        with pytest.raises(ValueError, match="inventory"):
            camera_stages(bad)
        # Keeping the count must not hide ANY missing partner, including the
        # final-stage clamp jaw/nuts rather than only the camera carrier.
        bad["CAMERA_UNRELATED"] = object()
        with pytest.raises(ValueError, match="inventory"):
            camera_stages(bad)


def test_mesh_hashes_detect_asset_change_without_xml_change(tmp_path):
    scene = tmp_path / "scene.xml"
    asset = tmp_path / "mesh.obj"
    scene.write_text('<mujoco><asset><mesh file="mesh.obj"/></asset></mujoco>')
    asset.write_text("v 0 0 0\n")
    xml = scene.read_bytes()
    before = mesh_assets(scene)
    asset.write_text("v 1 0 0\n")
    assert before != mesh_assets(scene)
    assert scene.read_bytes() == xml
    scene.write_text('<mujoco><asset><mesh file="../external.obj"/></asset></mujoco>')
    with pytest.raises(ValueError, match="outside"):
        mesh_assets(scene)
    scene.write_text('<mujoco><asset><mesh file="missing.obj"/></asset></mujoco>')
    with pytest.raises(FileNotFoundError):
        mesh_assets(Path(scene))
