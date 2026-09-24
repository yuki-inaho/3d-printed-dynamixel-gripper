import cadquery as cq
import pytest

from gripper_design.pg3 import GROUPS
from scripts import verify_pg3_service_stages as service
from scripts.verify_pg3_service_stages import driver_envelope, horn_l_key_envelope, mechanism_stages


def test_handle_grip_and_between_positions_obstacle_not_just_shaft():
    nominal = driver_envelope((0, 0, 0))
    shaft = cq.Solid.makeCylinder(1.5, 75, (0.05, 0, 0), (1, 0, 0))
    grip_obstacle = cq.Solid.makeBox(2, 2, 2, (90, 25, 0))
    assert shaft.distance(grip_obstacle) > 0
    assert nominal.intersect(grip_obstacle).Volume() > 7.9
    later = cq.Solid.makeBox(2, 2, 2, (185, 25, 0))
    assert nominal.distance(later) > 0
    assert driver_envelope((0, 0, 0), withdrawal=100).intersect(later).Volume() > 7.9


def test_missing_or_extra_inventory_rejected_before_any_geometry():
    proxy = cq.Solid.makeBox(1, 1, 1)
    shapes = {f"PG3_{name}": proxy for name in GROUPS}
    with pytest.raises(ValueError, match="inventory"):
        mechanism_stages(shapes | {"PG3_unreviewed": proxy})
    shapes.pop("PG3_frame")
    with pytest.raises(ValueError, match="inventory"):
        mechanism_stages(shapes)


def test_l_key_keeps_short_arm_rotation_and_grip_in_envelope():
    tool = horn_l_key_envelope((0, 0, 0))
    assert tool.distance(cq.Solid.makeBox(1, 1, 1, (10, 1, 0))) > 0
    assert tool.intersect(cq.Solid.makeBox(1, 1, 1, (40, 13, 0))).Volume() > 0.99
    assert tool.intersect(cq.Solid.makeBox(1, 1, 1, (50, 30, 0))).Volume() > 0.99
    assert tool.distance(cq.Solid.makeBox(1, 1, 1, (200, 13, 0))) > 0
    assert (
        horn_l_key_envelope((0, 0, 0), withdrawal=100)
        .intersect(cq.Solid.makeBox(1, 1, 1, (200, 13, 0)))
        .Volume()
        > 0.99
    )


def test_stages_retain_installed_parts_and_cover_every_bolt(monkeypatch):
    proxy = cq.Solid.makeBox(1, 1, 1)
    shapes = {f"PG3_{name}": proxy for name in GROUPS}
    shapes.update({"ARM_test_host": proxy, "CAMERA_future": proxy})
    monkeypatch.setattr(service, "profiles", lambda shape: None)
    monkeypatch.setattr(service, "pick", lambda *args: {"axis_yz_mm": (0, 0)})
    monkeypatch.setattr(service, "driver_envelope", lambda *args, **kwargs: proxy)
    stages = mechanism_stages(shapes)
    previous = {"ARM_test_host", "PG3_XL430_fixed", "PG3_XL430_horn"}
    covered = set()
    for obstacles, tools in stages.values():
        assert previous <= set(obstacles)
        assert "CAMERA_future" not in obstacles
        for name in tools:
            if name.startswith("TOOL_"):
                bolt = name.removeprefix("TOOL_")
                assert bolt in obstacles
                assert bolt not in covered
                assert f"WITHDRAWAL_{bolt}" in tools
                covered.add(bolt)
        previous = set(obstacles)
    expected = {n for n in shapes if "_bolt" in n or "_case_tapper" in n}
    assert covered == expected
    assert len(covered) == 18
    assert previous == set(shapes) - {"CAMERA_future", "PG3_pad_R", "PG3_pad_L"}
