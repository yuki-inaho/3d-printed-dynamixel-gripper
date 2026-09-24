import cadquery as cq
import pytest

from gripper_design.pg3 import PG3Model, shape_signature_difference, to_arm
from scripts.assembly_io import read_step
from scripts.review_pg3_local_contacts import reexpress, review_local_pairs


def test_reexpression_is_one_rigid_transform_not_per_part_alignment():
    source = cq.Solid.makeBox(3, 5, 7, (11, 13, 17))
    for angle in (25, 90, 135):
        world = to_arm(source.rotate((0, 0, 0), (0, 0, 1), angle - 90))
        restored = reexpress(world, angle)
        assert shape_signature_difference(source, restored)["vertex_distance_mm"] < 1e-6
        displaced = reexpress(world.translate((0.4, 0, 0)), angle)
        assert shape_signature_difference(source, displaced)["vertex_distance_mm"] > 0.39
    with pytest.raises(ValueError):
        reexpress(source, float("nan"))


@pytest.fixture(scope="module")
def pg3():
    return PG3Model()


@pytest.mark.parametrize("angle", [25, 90, 135])
def test_crank_contacts_clear_but_axial_penetrations_fail(pg3, angle):
    world = {f"PG3_{n}": to_arm(s) for n, s in pg3.at(angle).items()}
    pair = [("PG3_crank", "PG3_horn_bolt_0")]
    report = review_local_pairs(world, pair, angle)
    assert report["pairs"][0]["status"] == "PASS"
    for name, shift in (("PG3_horn_bolt_0", -0.5), ("PG3_pivot_drive_R_nut", 0.2)):
        moved = world | {name: world[name].translate((shift, 0, 0))}
        result = review_local_pairs(moved, [("PG3_crank", name)], angle)
        assert result["pairs"][0]["status"] == "FAIL"
        assert result["pairs"][0]["volume_mm3"] > 0.1


def test_containment_and_non_solid_remain_fail_or_unknown():
    outer = to_arm(cq.Solid.makeBox(10, 10, 10))
    inner = to_arm(cq.Solid.makeBox(2, 2, 2, (2, 2, 2)))
    shapes = {"outer": outer, "inner": inner, "shell": outer.Shells()[0]}
    report = review_local_pairs(shapes, [("outer", "inner"), ("outer", "shell")], 90)
    assert [p["status"] for p in report["pairs"]] == ["FAIL", "UNKNOWN"]


def test_exported_pose_does_not_inherit_in_memory_clearance(pg3, tmp_path):
    pair = [("PG3_crank", "PG3_horn_bolt_0")]
    assembly = cq.Assembly()
    source = pg3.at(25)
    for name in ("crank", "horn_bolt_0"):
        assembly.add(to_arm(source[name]), name=f"PG3_{name}")
    path = tmp_path / "pair.step"
    assembly.save(str(path))
    saved = {r.name: r.world for r in read_step(path)[2]}
    nominal = review_local_pairs(saved, pair, 25)
    bolt = "PG3_horn_bolt_0"
    moved = saved | {bolt: saved[bolt].translate((-0.5, 0, 0))}
    negative = review_local_pairs(moved, pair, 25)
    assert negative["pairs"][0]["status"] in {"FAIL", "ERROR"}
    if nominal["pairs"][0]["status"] == "PASS":
        assert negative["pairs"][0]["status"] == "FAIL"
    else:
        assert nominal["pairs"][0]["status"] == "ERROR"
