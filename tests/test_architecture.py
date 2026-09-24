from copy import deepcopy
from pathlib import Path

import pytest

from gripper_design.architecture import ArchitectureError, load_architecture, validate_architecture

SPEC_PATH = Path("specs/architecture.yaml")


def test_architecture_rejects_camera_on_roll_horn():
    architecture = load_architecture(SPEC_PATH)
    invalid = deepcopy(architecture)
    invalid["camera"]["mount_parent"]["part"] = "J5_output_horn"
    invalid["camera"]["kinematic_relationship"]["follows_cad_joint_J5_output_rotation"] = True

    with pytest.raises(ArchitectureError, match="P05-fixed"):
        validate_architecture(invalid)


def test_architecture_rejects_extra_jaw_motor_id():
    architecture = load_architecture(SPEC_PATH)
    invalid = deepcopy(architecture)
    invalid["jaw"]["physical_id"] = 6

    with pytest.raises(ArchitectureError, match="jaw actuator physical ID must be 5"):
        validate_architecture(invalid)


def test_current_architecture_is_valid_but_not_release_approved():
    architecture = load_architecture(SPEC_PATH)
    validate_architecture(architecture)

    assert architecture["scope"]["fabrication_approved"] is False
    assert architecture["scope"]["powered_operation_approved"] is False


def test_roll_is_not_reserved_after_user_removed_the_requirement():
    architecture = load_architecture(SPEC_PATH)
    assert architecture["roll"]["required"] is False
    assert architecture["roll"]["function_reserved"] is False
    assert architecture["roll"]["physical_id_candidate"] is None
    assert architecture["jaw"]["physical_id_candidate"] == 5
    assert architecture["jaw"]["physical_id"] == 5
    assert architecture["jaw"]["additional_motor_count"] == 0


def test_extra_motor_is_rejected():
    architecture = load_architecture(SPEC_PATH)
    architecture["jaw"]["additional_motor_count"] = 1
    with pytest.raises(ArchitectureError, match="no additional motor"):
        validate_architecture(architecture)


@pytest.mark.parametrize(
    "field,value",
    [
        ("required", True),
        ("function_reserved", True),
        ("physical_id_candidate", 5),
        ("may_drive_jaw", False),
    ],
)
def test_stale_roll_reservation_is_rejected(field, value):
    architecture = load_architecture(SPEC_PATH)
    architecture["roll"][field] = value
    with pytest.raises(ArchitectureError, match="roll is not required"):
        validate_architecture(architecture)
