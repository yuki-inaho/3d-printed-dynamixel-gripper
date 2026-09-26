"""Check frozen model semantics, collision geometry and safe output selection."""

import copy
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from validate_robot import (
    ROOT,
    ValidationError,
    check_model_contract,
    compare_native,
    load_json,
    local_mesh_path,
    validate,
    write_json_exclusive,
)


@pytest.fixture
def model(tmp_path):
    destination = tmp_path / "relocated-model"
    shutil.copytree(ROOT / "model", destination)
    return destination


@pytest.mark.parametrize(
    "corruption",
    [
        "widen_limit",
        "axis",
        "nan_limit",
        "effort",
        "mimic",
        "origin",
        "parent",
        "duplicate",
        "missing",
    ],
)
def test_frozen_joint_contract(corruption):
    robot = ET.parse(ROOT / "model/robot.urdf").getroot()
    joint = robot.find("joint[@name='joint4_wrist']")
    if corruption == "widen_limit":
        joint.find("limit").set("upper", "4")
    elif corruption == "axis":
        joint.find("axis").set("xyz", "1 0 0")
    elif corruption == "nan_limit":
        joint.find("limit").set("upper", "nan")
    elif corruption == "effort":
        joint.find("limit").set("effort", "1000")
    elif corruption == "mimic":
        ET.SubElement(joint, "mimic", {"joint": "joint1_yaw"})
    elif corruption == "origin":
        joint.find("origin").set("xyz", "0 0 0")
    elif corruption == "parent":
        joint.find("parent").set("link", "base_link")
    elif corruption == "duplicate":
        robot.append(copy.deepcopy(joint))
    else:
        robot.remove(joint)
    with pytest.raises(ValidationError):
        check_model_contract(robot, load_json(ROOT / "converter-config.json"))


@pytest.mark.parametrize(
    "corruption", ["collision_origin", "collision_mesh", "scale", "missing_collision"]
)
def test_collision_is_not_ignored(model, corruption):
    tree = ET.parse(model / "robot.urdf")
    link = tree.getroot().find("link[@name='camera_body']")
    collision = link.find("collision")
    if corruption == "collision_origin":
        collision.find("origin").set("xyz", "0 0 1")
    elif corruption == "collision_mesh":
        collision.find("geometry/mesh").set("filename", "assets/wrist.stl")
    elif corruption == "scale":
        collision.find("geometry/mesh").set("scale", "1000 1000 1000")
    else:
        link.remove(collision)
    tree.write(model / "robot.urdf")
    with pytest.raises(ValidationError):
        validate(model)


@pytest.mark.parametrize("corruption", ["duplicate_index", "count", "membership", "mesh_hash"])
def test_conversion_report_checked(model, corruption):
    path = model / "conversion.json"
    data = load_json(path)
    item = data["meshes"]["base_link"]
    if corruption == "duplicate_index":
        item["occurrence_indices"][1] = item["occurrence_indices"][0]
    elif corruption == "count":
        data["occurrences"] = 261
    elif corruption == "membership":
        item["occurrence_names"]["unassigned_part"] = 1
    else:
        item["sha256"] = "0" * 64
    path.write_text(json.dumps(data))
    with pytest.raises(ValidationError):
        validate(model)


@pytest.mark.parametrize(
    "filename",
    [
        "../other.stl",
        str(Path.cwd().anchor + "other.stl"),
        "https://example.invalid/mesh.stl",
        "assets\\mesh.stl",
    ],
)
def test_external_mesh_paths_rejected(tmp_path, filename):
    with pytest.raises(ValidationError):
        local_mesh_path(tmp_path, filename)


def test_symlink_cannot_escape_model(tmp_path):
    folder = tmp_path / "model"
    folder.mkdir()
    outside = tmp_path / "outside.stl"
    outside.write_text("not a mesh")
    (folder / "mesh.stl").symlink_to(outside)
    with pytest.raises(ValidationError):
        local_mesh_path(folder, "mesh.stl")


@pytest.mark.parametrize("text", ['{"a": 1, "a": 2}', '{"a": NaN}', '{"a": Infinity}'])
def test_invalid_json_fails_closed(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text)
    with pytest.raises(ValidationError):
        load_json(path)


def test_existing_evidence_never_overwritten(tmp_path):
    path = tmp_path / "report.json"
    path.write_text("original evidence\n")
    with pytest.raises(FileExistsError):
        write_json_exclusive(path, {"status": "PASS"})
    assert path.read_text() == "original evidence\n"


def test_member_failure_rejected_independently_of_version_metadata():
    robot = ET.parse(ROOT / "model/robot.urdf").getroot()
    data = load_json(ROOT.parent / "reports/native-pose-transforms.json")
    # Keep valid V2 metadata/hashes but make one declared rigid member move 1 mm.
    data["cases"][0]["instances"]["jaw_l"]["max_member_translation_delta_mm"] = 1
    with pytest.raises(ValidationError, match="rigidity"):
        compare_native(robot, data)


def test_cli_checks_selected_model_and_protects_old_results(model, tmp_path):
    output = tmp_path / "new-report.json"
    archived = (ROOT / "validation.json").read_bytes()
    command = [
        sys.executable,
        str(ROOT / "validate_robot.py"),
        "--model",
        str(model),
        "--output",
        str(output),
    ]
    passed = subprocess.run(
        command, cwd=tmp_path, text=True, capture_output=True, timeout=60, check=False
    )
    assert passed.returncode == 0, passed.stdout + passed.stderr
    assert load_json(output)["model_directory"] == model.name
    original = output.read_bytes()
    repeated = subprocess.run(
        command, cwd=tmp_path, text=True, capture_output=True, timeout=30, check=False
    )
    assert repeated.returncode == 1 and "already exists" in repeated.stdout
    assert output.read_bytes() == original
    tree = ET.parse(model / "robot.urdf")
    tree.getroot().find("joint[@name='joint4_wrist']/limit").set("upper", "4")
    tree.write(model / "robot.urdf")
    failed = subprocess.run(
        command[:-2], cwd=tmp_path, text=True, capture_output=True, timeout=30, check=False
    )
    assert failed.returncode == 1 and '"status": "FAIL"' in failed.stdout
    assert (ROOT / "validation.json").read_bytes() == archived
