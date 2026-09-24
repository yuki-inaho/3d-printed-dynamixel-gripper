import cadquery as cq

from scripts.triage_pg3_contacts import category, source_signature


def test_inherited_signature_rejects_shift_and_changed_wall():
    source = cq.Solid.makeBox(10, 12, 14)
    assert source_signature(source.copy(), source)["status"] == "SIGNATURE_MATCH"
    assert source_signature(source.translate((1, 0, 0)), source)["status"] == "SOURCE_MISMATCH"
    cut = source.cut(cq.Solid.makeBox(1, 12, 14))
    assert source_signature(cut, source)["status"] == "SOURCE_MISMATCH"
    assert source_signature(source, None)["status"] == "NO_UNCHANGED_SOURCE_CLAIM"


def test_contact_categories_are_symmetric_and_not_clearance_verdicts():
    assert (
        category("ARM_M06_ref02", "PG3_XL430_fixed")
        == category("PG3_XL430_fixed", "ARM_M06_ref02")
        == "supplier_internal_vs_partitioned_motor"
    )
    assert category("ARM_M05_ref02", "PG3_XL430_fixed") == "UNCLASSIFIED_REQUIRES_REVIEW"
    assert category("ARM_M06_ref99", "PG3_XL430_fixed") == "UNCLASSIFIED_REQUIRES_REVIEW"
    assert category("PG3_crank", "PG3_horn_bolt_0").startswith("inherited_pg3")
