from pathlib import Path

import yaml


def read_spec(path):
    return yaml.safe_load(Path(path).read_text())


def test_active_pg3_catalog_separates_source_from_installation_candidate():
    project = read_spec("specs/project.yaml")
    variants = read_spec(project["variant_catalog"])["variants"]
    assert "R-10" in project["requirements"]
    assert project["active_variant"] == "pg3_c92_j28_c9"
    variant = variants[project["active_variant"]]
    assert variant["implementation"] == "gripper_design/pg3.py"
    candidate = variant["installation_candidate"]
    assert candidate["implementation"] == "gripper_design/pg3_id5.py"
    assert candidate["specification"] == project["active_installation_spec"]
    for key in (
        "implementation",
        "specification",
        "design_document",
        "review_script",
    ):
        assert Path(candidate[key]).is_file()
    assert candidate["source_archive_modified"] is False
    assert candidate["p05_modified"] is False
    assert candidate["downstream_motor_removed"] is True
    assert candidate["additional_motor_count"] == 0
    assert candidate["candidate_bom"] is None
    assert candidate["simulation"] is None
    historical = variant["historical_installation_candidate"]
    assert historical["implementation"] == "gripper_design/pg3_installation.py"
    assert Path(historical["candidate_bom"]).is_file()
    assert candidate["whole_arm_fit_approved"] is False
    assert candidate["physical_assembly_verified"] is False
    assert project["release"]["cad_accepted"] is False
    assert project["release"]["fabrication_approved"] is False
    assert project["release"]["powered_operation_approved"] is False


def test_sep24_user_decisions_are_not_fabrication_approval():
    project = read_spec("specs/project.yaml")
    assert project["camera"]["purchase_status"] == "not_purchased"
    assert project["camera"]["mounting_pattern_mm"] == [28.0, 28.0]
    assert project["camera"]["model"] is None
    assert project["performance"]["object_definition"] == "cube"
    assert project["performance"]["cube_edge_mm"] is None
    assert project["performance"]["roll_required"] is False
    permission = project["p05_cable_relief_authorization"]
    assert permission["candidate_design_allowed"] is True
    assert permission["source_mutation_allowed"] is False
    assert permission["fabrication_approved"] is False
    assert project["hardware"]["oem_m2_6x5_tapper_possession"] == "absent_or_unknown"


def test_id5_only_is_confirmed_without_claiming_observed_cad_mapping():
    project = read_spec("specs/project.yaml")
    assert project["actuator"]["role"] == "gripper_open_close"
    assert project["integration"]["additional_gripper_motor_count"] == 0
    assert project["integration"]["physical_to_cad"]["5"] is None
