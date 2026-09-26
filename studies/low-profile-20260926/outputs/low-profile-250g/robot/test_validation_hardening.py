"""Regression controls for false acceptance found during the handoff audit."""

import copy
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest
from validate_robot import ROOT, compare_native


@pytest.fixture
def evidence():
    return ET.parse(ROOT / "model/robot.urdf").getroot(), json.loads(
        (ROOT.parent / "reports/native-pose-transforms.json").read_text()
    )


def test_duplicate_pose_is_not_eleven_pose_coverage(evidence):
    robot, data = evidence
    data["cases"] = [copy.deepcopy(data["cases"][0]) for _ in range(11)]
    with pytest.raises((AssertionError, ValueError)):
        compare_native(robot, data)


def test_wrong_pose_name_rejected(evidence):
    robot, data = evidence
    data["cases"][0]["name"] = "unapproved_pose"
    with pytest.raises((AssertionError, ValueError)):
        compare_native(robot, data)


@pytest.mark.parametrize("corruption", ["bottom_row", "scaled_rotation", "nan", "infinity"])
def test_invalid_transform_rejected(evidence, corruption):
    robot, data = evidence
    matrix = data["cases"][0]["instances"]["camera_body"]["transform_m"]
    if corruption == "bottom_row":
        matrix[15] = 7.0
    elif corruption == "scaled_rotation":
        for i in (0, 5, 10):
            matrix[i] *= 2.0
    elif corruption == "nan":
        matrix[3] = float("nan")
    else:
        matrix[3] = float("inf")
    with pytest.raises((AssertionError, ValueError)):
        compare_native(robot, data)


def test_body_count_not_just_representative_transform(evidence):
    robot, data = evidence
    data["cases"][0]["instances"]["jaw_l"]["body_count"] -= 1
    with pytest.raises((AssertionError, ValueError)):
        compare_native(robot, data)


def test_negative_diagnostic_is_not_zero_error(evidence):
    robot, data = evidence
    data["cases"][0]["instances"]["jaw_l"]["max_member_translation_delta_mm"] = -1.0
    with pytest.raises((AssertionError, ValueError)):
        compare_native(robot, data)


def test_source_pose_hash_must_match_file(evidence):
    robot, data = evidence
    data["cases"][0]["step_sha256"] = "0" * 64
    with pytest.raises((AssertionError, ValueError)):
        compare_native(robot, data)


def test_wrong_onshape_version_rejected(evidence):
    robot, data = evidence
    data["baseline_version"] = "4577cc931e9bc290e2b31032"
    with pytest.raises((AssertionError, ValueError)):
        compare_native(robot, data)


def test_extra_group_is_not_silently_ignored(evidence):
    robot, data = evidence
    data["cases"][0]["instances"]["undeclared_group"] = copy.deepcopy(
        data["cases"][0]["instances"]["camera_body"]
    )
    with pytest.raises((AssertionError, ValueError)):
        compare_native(robot, data)


def test_optimized_python_cannot_disable_validation(tmp_path, evidence):
    _, data = evidence
    data["cases"] = [copy.deepcopy(data["cases"][0]) for _ in range(11)]
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(data))
    code = (
        "import json,sys,xml.etree.ElementTree as E; "
        "from validate_robot import ROOT,compare_native; "
        "compare_native(E.parse(ROOT/'model/robot.urdf').getroot(),"
        "json.load(open(sys.argv[1])))"
    )
    process = subprocess.run(
        [sys.executable, "-O", "-c", code, str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert process.returncode != 0, "python -O incorrectly accepted duplicate pose evidence"
