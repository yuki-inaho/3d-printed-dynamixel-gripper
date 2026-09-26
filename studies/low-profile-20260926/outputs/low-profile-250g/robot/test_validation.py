"""Negative controls exercise the same native/FK acceptance routine."""

import copy
import json
import xml.etree.ElementTree as ET

import pytest
from validate_robot import ROOT, compare_native


@pytest.fixture
def inputs():
    return ET.parse(ROOT / "model/robot.urdf").getroot(), json.loads(
        (ROOT.parent / "reports/native-pose-transforms.json").read_text()
    )


def test_actual_v2_poses(inputs):
    assert len(compare_native(*inputs)) == 11


def test_reject_real_v1_pad_misassignment(inputs):
    robot, _ = inputs
    bad = json.loads(
        (
            ROOT.parent / "reports/v1-pad-misassigned/native-pose-transforms.json"
        ).read_text()
    )
    with pytest.raises(AssertionError):
        compare_native(robot, bad)


def test_reject_reversed_active_axis(inputs):
    robot, native = inputs
    bad = copy.deepcopy(robot)
    bad.find("joint[@name='joint1_yaw']/axis").set("xyz", "0 0 1")
    with pytest.raises(AssertionError):
        compare_native(bad, native)


def test_reject_metre_millimetre_placement(inputs):
    robot, native = inputs
    bad = copy.deepcopy(native)
    case = next(
        case for case in bad["cases"] if case["name"] == "small_joint2_shoulder"
    )
    matrix = case["instances"]["camera_body"]["transform_m"]
    assert max(abs(matrix[index]) for index in (3, 7, 11)) > 0.001
    for index in (3, 7, 11):
        matrix[index] *= 1000
    with pytest.raises(AssertionError):
        compare_native(robot, bad)
