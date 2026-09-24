from copy import deepcopy

import pytest

from scripts.check_pg3_bom import reconcile, require_digest


def fixture():
    return {
        "scope_prefixes": ["PG3_", "CAMERA_", "ARM_P06_"],
        "items": [
            {"id": "frame", "quantity": 1, "patterns": ["PG3_frame"]},
            {"id": "caps", "quantity": 2, "patterns": ["PG3_cap_?"]},
            {
                "id": "jaw_motor",
                "quantity": 1,
                "patterns": ["PG3_XL430_fixed", "PG3_XL430_horn"],
                "representation": "one_motor_fixed_and_horn",
            },
        ],
    }, ["PG3_frame", "PG3_cap_U", "PG3_cap_D", "PG3_XL430_fixed", "PG3_XL430_horn", "ARM_P05"]


def test_full_coverage_counts_physical_motor_once():
    spec, names = fixture()
    result = reconcile(spec, names)
    assert result["covered_occurrence_count"] == 5
    assert result["physical_item_count"] == 4
    assert result["excluded_occurrences"] == ["ARM_P05"]
    assert result["fabrication_approved"] is False


@pytest.mark.parametrize(
    "defect", ["missing", "extra", "duplicate", "quantity", "motor", "out_of_scope"]
)
def test_bad_inventory_is_not_a_complete_bom(defect):
    spec, names = fixture()
    if defect == "missing":
        names.remove("PG3_cap_U")
    elif defect == "extra":
        names.append("CAMERA_unlisted")
    elif defect == "duplicate":
        row = deepcopy(spec["items"][0])
        row["id"] = "another_frame"
        spec["items"].append(row)
    elif defect == "quantity":
        spec["items"][1]["quantity"] = 1
    elif defect == "motor":
        spec["items"][1]["representation"] = "one_motor_fixed_and_horn"
    else:
        spec["items"].append({"id": "old", "quantity": 1, "patterns": ["ARM_P05"]})
    with pytest.raises(ValueError):
        reconcile(spec, names)


def test_duplicate_saved_names_are_rejected():
    spec, names = fixture()
    with pytest.raises(ValueError, match="duplicate"):
        reconcile(spec, names + [names[0]])


def test_other_revision_cannot_reuse_inventory_receipt(tmp_path):
    import hashlib

    path = tmp_path / "assembly.step"
    path.write_bytes(b"version one")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert require_digest(path, expected) == expected
    path.write_bytes(b"different geometry with same names")
    with pytest.raises(ValueError, match="SHA"):
        require_digest(path, expected)


def test_scope_cannot_be_shrunk_to_hide_missing_parts():
    spec, names = fixture()
    spec["scope_prefixes"] = ["PG3_"]
    with pytest.raises(ValueError, match="scope"):
        reconcile(spec, names)
