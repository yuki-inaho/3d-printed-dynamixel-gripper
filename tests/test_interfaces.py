from pathlib import Path

import pytest

from gripper_design.interfaces import (
    InterfaceMismatch,
    load_interface_contract,
    validate_bolt_circle,
    validate_contract_geometry,
)

SPEC_PATH = Path("specs/interfaces_all_xl430.yaml")


def test_donor_pcd12_rejected_against_xl430_pcd16():
    contract = load_interface_contract(SPEC_PATH)
    donor = contract["negative_control"]["donor_interface"]
    reference = contract["negative_control"]["all_xl430_reference"]

    with pytest.raises(InterfaceMismatch, match="radial mismatch 2.000 mm"):
        validate_bolt_circle(donor, reference)


def test_r3_self_pattern_matches():
    contract = load_interface_contract(SPEC_PATH)
    output = contract["servo_interfaces"]["J5"]["output_side"]
    assert validate_bolt_circle(output, output) == pytest.approx(0.0)


def test_all_xl430_contract_vectors_reproduce_pcd():
    contract = load_interface_contract(SPEC_PATH)
    validate_contract_geometry(contract)
