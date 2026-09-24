import hashlib
import math
import zipfile

import cadquery as cq
import numpy as np
import pytest

from gripper_design.pg2 import import_archive, verify_intake
from gripper_design.pg3 import PG3Model, group_for, opening_mm, position_mm, to_arm


def test_pg3_uses_own_dimensions_and_angle_limits():
    assert opening_mm(25) == pytest.approx(48.895, abs=0.001)
    assert opening_mm(135) == pytest.approx(0.927, abs=0.001)
    for angle in (24, 136, float("nan")):
        with pytest.raises(ValueError):
            opening_mm(angle)
    for angle in np.linspace(25, 135, 21):
        a = math.radians(angle)
        assert math.hypot(position_mm(angle) - 14 * math.cos(a), 14 * math.sin(a)) == pytest.approx(
            24
        )


def test_unknown_component_is_not_silently_fixed():
    with pytest.raises(ValueError, match="unknown"):
        group_for("unreviewed_bracket")


@pytest.fixture(scope="module")
def pg3():
    return PG3Model()


@pytest.mark.parametrize("angle,pose", [(25, "open"), (90, "mid"), (135, "closed")])
def test_saved_pose_matches_independent_rigid_motion(pg3, angle, pose):
    result = pg3.compare_saved(angle, pose)
    assert result["occurrence_count"] == 57
    assert result["maximum_vertex_distance_mm"] < 1e-6
    assert result["maximum_volume_error_mm3"] < 1e-4
    assert abs(result["measured_opening_mm"] - opening_mm(angle)) < 1e-6


def test_motor_transform_preserves_righthanded_axes():
    p = cq.Vertex.makeVertex(0, 0, 19)
    assert to_arm(p).Center().toTuple() == pytest.approx((18.8, 234.9, 164.6))


def test_pg3_explicit_archive_layout_and_reverify(tmp_path):
    archive = tmp_path / "c9.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("PG3_C92_J28/test.txt", b"sample")
        target.writestr(
            "PG3_C92_J28/SHA256SUMS.txt", hashlib.sha256(b"sample").hexdigest() + "  test.txt\n"
        )
    with pytest.raises(ValueError):
        import_archive(archive, tmp_path / "wrong")
    import_archive(
        archive, tmp_path / "correct", archive_root="PG3_C92_J28", manifest_name="SHA256SUMS.txt"
    )
    root = tmp_path / "correct/PG3_C92_J28"
    assert verify_intake(root)["verified_file_count"] == 1
    (root / "test.txt").write_text("corrupt")
    with pytest.raises(ValueError):
        verify_intake(root)


def test_signature_detects_one_mm_wrong_placement(pg3):
    from gripper_design.pg3 import shape_signature_difference

    shape = pg3.neutral["frame"]
    assert (
        shape_signature_difference(shape, shape.translate((1, 0, 0)))["vertex_distance_mm"] > 0.99
    )


def test_boolean_scan_has_positive_negative_and_unknown_controls():
    from scripts.review_pg3 import inspect_pairs

    box = cq.Workplane("XY").box(10, 10, 10).val()
    shapes = {
        "body": box,
        "bolt": box,
        "remote": box.translate((20, 0, 0)),
        "shell": box.Shells()[0],
    }
    r = inspect_pairs(shapes, [("body", "bolt"), ("body", "remote"), ("body", "shell")])
    assert [row["status"] for row in r["pairs"]] == ["FAIL", "PASS", "UNKNOWN"]
    assert r["pairs"][0]["volume_mm3"] == pytest.approx(1000)
    assert r["operand_controls"]["body"]["passed"]


def test_arm_preserves_motor_support_and_has_one_replacement_motor(pg3):
    from gripper_design.pg3 import arm_assembly

    shapes = arm_assembly(pg3, 90)
    assert "ARM_P06_fixed_gripper_XL430" in shapes
    assert "ARM_P07_moving_gripper_XL430" not in shapes
    assert "ARM_M06_ref00" not in shapes
    assert "PG3_XL430_fixed" in shapes and "PG3_XL430_horn" in shapes
    assert "CAMERA_REFERENCE_UNCONFIRMED" in shapes
    assert len(shapes) == 293


def test_mujoco_closed_loop_and_injected_joint_error(tmp_path, pg3):
    import xml.etree.ElementTree as ET

    import mujoco

    from simulation.pg3_scene import set_pose, write_scene

    path = write_scene(pg3, tmp_path / "scene")
    model = mujoco.MjModel.from_xml_path(str(path))
    data = mujoco.MjData(model)
    assert model.nv == 6 and model.neq == 2
    positions = []
    for angle in (25, 90, 135):
        result = set_pose(model, data, angle)
        assert result["closure_residual_mm"] < 1e-7
        assert result["measured_pad_gap_mm"] == pytest.approx(opening_mm(angle))
        positions.append(data.camera("camera_proxy").xpos.copy())
    assert np.allclose(positions[0], positions[2])
    before_pad = data.site("pad_inner_R").xpos.copy()
    before_rotation = data.camera("camera_proxy").xmat.copy()
    set_pose(model, data, 135, 30)
    assert not np.allclose(before_pad, data.site("pad_inner_R").xpos)
    assert np.allclose(positions[0], data.camera("camera_proxy").xpos)
    assert np.allclose(before_rotation, data.camera("camera_proxy").xmat)
    data.qpos[model.joint("slide_R").qposadr[0]] += 0.001
    mujoco.mj_forward(model, data)
    assert np.linalg.norm(
        data.site("endpoint_R").xpos - data.site("carriage_pin_R").xpos
    ) * 1000 == pytest.approx(1)
    # A wrong link endpoint and an incorrectly parented camera must be observable.
    model.site_pos[model.site("endpoint_R").id, 0] += 0.001
    assert set_pose(model, data, 90)["closure_residual_mm"] == pytest.approx(1)
    tree = ET.parse(path)
    world = tree.find("worldbody")
    camera_body = world.find("body[@name='P05_camera_fixed']")
    world.remove(camera_body)
    world.find("body[@name='J5_roll_diagnostic']").append(camera_body)
    wrong_path = path.with_name("wrong_parent.xml")
    tree.write(wrong_path, encoding="unicode")
    wrong_model = mujoco.MjModel.from_xml_path(str(wrong_path))
    wrong_data = mujoco.MjData(wrong_model)
    set_pose(wrong_model, wrong_data, 90, 0)
    camera_before = wrong_data.camera("camera_proxy").xpos.copy()
    set_pose(wrong_model, wrong_data, 90, 30)
    assert not np.allclose(camera_before, wrong_data.camera("camera_proxy").xpos)


def test_output_audit_rejects_empty_and_altered_evidence(tmp_path):
    from gripper_design.pg2 import digest
    from scripts.audit_pg3_run import check_manifest

    with pytest.raises(ValueError, match="empty"):
        check_manifest(tmp_path, {})
    path = tmp_path / "artifact.json"
    path.write_text("original")
    manifest = {path.name: digest(path)}
    check_manifest(tmp_path, manifest)
    path.write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        check_manifest(tmp_path, manifest)


def test_pair_scan_distance_proof_never_accepts_containment_or_shell_occupancy():
    from scripts.review_pg3 import inspect_pairs

    ring = cq.Workplane("XY").circle(5).circle(3).extrude(5).val()
    pin = cq.Solid.makeCylinder(1, 5)
    block = cq.Solid.makeBox(20, 20, 20, (-10, -10, -5))
    shapes = {"ring": ring, "pin": pin, "block": block, "shell": block.Shells()[0]}
    result = inspect_pairs(shapes, [("ring", "pin"), ("block", "pin"), ("shell", "pin")])
    clear, contained, shell = result["pairs"]
    assert clear["reason"] == "solid_distance_separated"
    assert clear["distance_mm"] == pytest.approx(2)
    assert contained["status"] == "FAIL"
    assert shell["status"] == "UNKNOWN"


def test_pair_scan_rejects_one_mm_penetration_and_nan_distance(monkeypatch):
    from scripts.review_pg3 import inspect_pairs

    a = cq.Solid.makeBox(10, 10, 10)
    b = a.translate((9, 0, 0))
    row = inspect_pairs({"a": a, "b": b}, [("a", "b")])["pairs"][0]
    assert row["status"] == "FAIL" and row["volume_mm3"] == pytest.approx(100)
    monkeypatch.setattr(cq.Shape, "distance", lambda self, other: float("nan"))
    row = inspect_pairs({"a": a, "b": b}, [("a", "b")])["pairs"][0]
    assert row["status"] == "ERROR"


def test_failed_boolean_operand_can_only_pass_with_conservative_enclosure(monkeypatch):
    from scripts.review_pg3 import inspect_pairs

    ring = cq.Workplane("XY").rect(20, 20).rect(10, 10).extrude(10).val()
    inside = cq.Solid.makeBox(10, 10, 10, (-5, -5, 0))
    # Inject a failed independent-copy control without changing original geometry.
    monkeypatch.setattr(inside, "copy", lambda: inside.translate((100, 0, 0)))
    result = inspect_pairs({"ring": ring, "inside": inside}, [("ring", "inside")])
    row = result["pairs"][0]
    assert row["status"] == "PASS"
    assert row["reason"] == "conservative_enclosure_boolean_clear"
    assert row["enclosed_operands"] == ["inside"]
    assert not result["operand_controls"]["inside"]["passed"]
    wrong = inside.translate((1, 0, 0))
    monkeypatch.setattr(wrong, "copy", lambda: wrong.translate((100, 0, 0)))
    row = inspect_pairs({"ring": ring, "inside": wrong}, [("ring", "inside")])["pairs"][0]
    assert row["status"] == "ERROR"
    assert row["conservative_intersection_mm3"] > 90
