from copy import deepcopy

import pytest

from scripts.review_pg3_supplier_inventory import describe, match_envelopes


def record(name, x=0, solid=True):
    return {
        "id": name,
        "bounds_mm": [x, 0, 0, x + 1, 2, 3],
        "solid_only": solid,
        "solid_count": int(solid),
        "volume_mm3": 6 if solid else None,
        "area_mm2": 22,
    }


def test_reordered_solid_shell_inventory_is_not_zipped_by_index():
    source = [record("source-solid"), record("source-shell", solid=False)]
    target = [record("target-shell", solid=False), record("target-solid")]
    rows = match_envelopes(source, target)
    assert [r["candidate_id"] for r in rows] == ["target-solid", "target-shell"]
    assert not any(r["material_equivalence_proven"] for r in rows)


def test_same_bounds_with_missing_material_is_not_equivalence():
    original, changed = record("a"), record("b")
    changed["volume_mm3"] = 1
    row = match_envelopes([original], [changed])[0]
    assert row["volume_difference_mm3"] == 5
    assert row["material_equivalence_proven"] is False


def test_actual_internal_cavity_keeps_bounds_but_changes_material():
    import cadquery as cq

    full = cq.Solid.makeBox(10, 10, 10)
    hollow = full.cut(cq.Solid.makeBox(2, 2, 2, (4, 4, 4)))
    first = describe("full", full, "fixture")
    second = describe("hollow", hollow, "fixture")
    row = match_envelopes([first], [second])[0]
    assert row["max_bbox_error_mm"] == 0
    assert row["volume_difference_mm3"] == pytest.approx(8)
    assert row["area_difference_mm2"] == pytest.approx(24)
    assert row["material_equivalence_proven"] is False


@pytest.mark.parametrize(
    "defect", ["missing", "duplicate_id", "ambiguous", "shifted", "nan", "reversed", "wrong_kind"]
)
def test_invalid_correspondence_is_rejected(defect):
    source = [record("s1"), record("s2", x=10)]
    target = [record("t1"), record("t2", x=10)]
    if defect == "missing":
        target.pop()
    elif defect == "duplicate_id":
        target[1]["id"] = "t1"
    elif defect == "ambiguous":
        target[1] = deepcopy(target[0])
        target[1]["id"] = "t2"
    elif defect == "shifted":
        target[0] = record("t1", x=1)
    elif defect == "nan":
        target[0]["bounds_mm"][0] = float("nan")
    elif defect == "reversed":
        target[0]["bounds_mm"][0] = 2
    else:
        target[0] = record("t1", solid=False)
    with pytest.raises(ValueError):
        match_envelopes(source, target)
