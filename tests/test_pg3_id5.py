import cadquery as cq
import pytest

from gripper_design.build import _source_rows
from gripper_design.pg3 import SOURCE, PG3Model, shape_signature_difference
from gripper_design.pg3_id5 import assemble, inventory_contract, to_id5
from scripts.review_pg3 import inspect_pairs


@pytest.fixture(scope="module")
def model():
    return PG3Model()


@pytest.fixture(scope="module")
def mid(model):
    return assemble(model, 90)


def test_motor_pose_matches_m05_not_m06():
    source = cq.importers.importStep(
        str(SOURCE / "reference/C7/reference/XL430_from_supplied_arm.step")
    ).val()
    target = next(r.world for r in _source_rows() if r.name == "M05_ref00")
    placed = to_id5(source)
    correct = shape_signature_difference(placed, target)
    assert correct["vertex_distance_mm"] < 1e-6
    assert correct["volume_error_mm3"] < 1e-4
    assert correct["face_count_equal"]
    assert (
        shape_signature_difference(placed.translate((1, 0, 0)), target)["vertex_distance_mm"] > 0.9
    )


def test_inventory_has_one_terminal_motor_and_preserved_upstream(mid):
    report = inventory_contract(mid)
    assert report["physical_motor_count_by_design"] == 5
    assert report["additional_terminal_motor_count"] == 0
    assert report["observed_physical_mapping_verified"] is False
    for row in _source_rows():
        if f"ARM_{row.name}" in mid:
            assert (
                shape_signature_difference(mid[f"ARM_{row.name}"], row.world)["vertex_distance_mm"]
                < 1e-6
            )


@pytest.mark.parametrize("change", ["extra_motor", "missing_upstream", "missing_horn"])
def test_wrong_inventory_is_rejected(mid, change):
    wrong = dict(mid)
    if change == "extra_motor":
        wrong["ARM_M06_ref00"] = mid["PG3_XL430_fixed"]
    else:
        wrong.pop("ARM_M01_ref00" if change == "missing_upstream" else "PG3_XL430_horn")
    with pytest.raises(ValueError, match="inventory"):
        inventory_contract(wrong)


def test_p05_does_not_intersect_new_frame_or_jaws(mid):
    partners = ["PG3_frame", "PG3_finger_L", "PG3_finger_R", "PG3_crank"]
    result = inspect_pairs(mid, [("ARM_P05_wrist_XL430", p) for p in partners])
    assert result["counts"] == {"PASS": 4}
