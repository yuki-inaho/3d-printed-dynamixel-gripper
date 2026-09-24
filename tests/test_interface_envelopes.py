import cadquery as cq
import pytest

from gripper_design.interface_envelopes import axial_boss_cover
from scripts.review_pg3_components import inspect_components


def motor():
    body = cq.Solid.makeBox(20, 10, 20, (-10, -10, -10))
    boss = cq.Solid.makeCylinder(4, 1.7, (0, 0, 0), (0, 1, 0))
    chamfer = cq.Solid.makeCone(4, 3.7, 0.3, (0, 1.7, 0), (0, 1, 0))
    return body.fuse(boss, chamfer)


def test_analytic_boundary_cover_and_intrusion_control():
    source = motor()
    cover, evidence = axial_boss_cover(source, 1, 0, (0, 0), 4)
    assert len(evidence["all_boundary_faces"]) == len(source.Faces())
    material = cq.Compound.makeCompound(list(cover.values()))
    ring = cq.Solid.makeCylinder(7, 3, (0, 0, 0), (0, 1, 0)).cut(
        cq.Solid.makeCylinder(5.5, 3, (0, 0, 0), (0, 1, 0))
    )
    assert inspect_components(material, ring)["status"] == "PASS"
    assert inspect_components(material, ring.translate((2, 0, 0)))["status"] == "FAIL"


def test_wrong_radius_and_extra_protruding_material_are_rejected():
    with pytest.raises(ValueError, match="radius"):
        axial_boss_cover(motor(), 1, 0, (0, 0), 3.9)
    extra = cq.Compound.makeCompound([motor(), cq.Solid.makeBox(1, 1, 1, (8, 0, 0))])
    with pytest.raises(ValueError):
        axial_boss_cover(extra, 1, 0, (0, 0), 4)


def test_allowed_thread_region_does_not_hide_off_axis_or_deep_intrusion():
    from gripper_design.interface_envelopes import bounded_contact

    cover = {"case": cq.Solid.makeBox(20, 20, 10, (-10, -10, -10))}
    roi = cq.Solid.makeCylinder(1.3, 4, (0, 0, -4))
    bolt = cq.Solid.makeCylinder(1.3, 7, (0, 0, -3.5)).fuse(
        cq.Solid.makeCylinder(2.5, 2, (0, 0, 3.5))
    )
    assert bounded_contact(bolt, roi, cover)["outside_allowed_region_clear"]
    assert not bounded_contact(bolt.translate((1, 0, 0)), roi, cover)[
        "outside_allowed_region_clear"
    ]
    assert not bounded_contact(bolt.translate((0, 0, -2)), roi, cover)[
        "outside_allowed_region_clear"
    ]


def test_actual_p06_m05_clear_and_bad_alignment_is_not_waived():
    from gripper_design.build import _source_rows
    from gripper_design.pg3_installation import support_candidate

    motor_shape = next(r.world for r in _source_rows() if r.name == "M05_ref00")
    cover, _ = axial_boss_cover(motor_shape, 1, 183.9, (-0.2, 164.6), 4)
    material = cq.Compound.makeCompound(list(cover.values()))
    support = support_candidate()
    assert inspect_components(material, support)["status"] == "PASS"
    assert inspect_components(material, support.translate((2, 0, 0)))["status"] == "FAIL"
