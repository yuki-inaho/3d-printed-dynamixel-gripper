"""Negative controls on complete occurrence grouping, independent of CAD imports."""

import copy

import pytest
from replay_step import derive_case, group_members, replay
from validate_robot import ROOT, ValidationError, load_json


@pytest.fixture
def occurrences():
    data = load_json(ROOT.parent / "reports/native-step-zero.json")
    for part in data["parts"]:
        part["body_type"] = "solid" if part["solids"] else "sheet"
    groups = load_json(ROOT.parent / "reports/expected-groups.json")["groups"]
    return data, groups


@pytest.mark.parametrize(
    "corruption", ["missing", "extra", "body_type", "local_geometry", "topology", "ambiguous_name"]
)
def test_all_occurrences_must_match(occurrences, corruption):
    data, groups = occurrences
    reference = copy.deepcopy(data["parts"])
    parts = data["parts"]
    if corruption == "missing":
        parts.pop()
    elif corruption == "extra":
        parts.append(copy.deepcopy(parts[0]))
    elif corruption == "body_type":
        parts[0]["body_type"] = "solid" if parts[0]["body_type"] == "sheet" else "sheet"
    elif corruption == "local_geometry":
        parts[0]["local_bounds_mm"][0] += 1
    elif corruption == "topology":
        parts[0]["faces"] += 1
    else:
        # Keep the aggregate multiset unchanged but assign a repeated base name across links.
        base_names = [p["name"] for p in groups["base_link"]]
        duplicate = next(name for name in base_names if base_names.count(name) > 1)
        index = next(i for i, p in enumerate(groups["base_link"]) if p["name"] == duplicate)
        groups["jaw_l"].append(groups["base_link"].pop(index))
    with pytest.raises(ValidationError):
        group_members(parts, reference, groups)


def test_one_bad_member_cannot_hide_behind_a_good_representative(occurrences):
    data, groups = occurrences
    reference = copy.deepcopy(data["parts"])
    names = {p["name"] for p in groups["jaw_l"]}
    member = next(p for p in data["parts"] if p["name"] in names)
    member["placement_mm"][0][3] += 1
    target = load_json(ROOT.parent / "reports/native-pose-targets.json")["cases"][0]
    joints = load_json(ROOT / "joint-definitions.json")[:5]
    with pytest.raises(ValidationError, match="move differently"):
        derive_case(target, data, reference, groups, joints)


def test_replay_refuses_existing_output_before_reading(tmp_path):
    output = tmp_path / "old-results"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("original")
    with pytest.raises(FileExistsError):
        replay(ROOT.parent, output)
    assert sentinel.read_text() == "original"
