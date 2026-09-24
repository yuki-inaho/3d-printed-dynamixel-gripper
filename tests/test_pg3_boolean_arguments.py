import cadquery as cq

from scripts.probe_pg3_saved_boolean import analyze_argument


def test_input_diagnostic_distinguishes_valid_box_from_overlapping_solids():
    box = cq.Solid.makeBox(4, 4, 4)
    good = analyze_argument(box)
    assert good["topology_valid"] is True
    assert good["argument_faults"] == []
    assert good["self_common_mm3"] == good["volume_mm3"]
    assert good["self_cut_mm3"] == 0
    # BRepCheck validity does not reject overlapping solids in a compound.
    overlap = cq.Compound.makeCompound([box, box.translate((2, 0, 0))])
    bad = analyze_argument(overlap)
    assert bad["topology_valid"] is True
    assert any("SelfIntersect" in r["status"] for r in bad["argument_faults"])
    assert good["installation_approved"] is False
    assert bad["installation_approved"] is False
