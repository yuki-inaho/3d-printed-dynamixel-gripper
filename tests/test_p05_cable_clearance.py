"""Challenge a wider local window against the actual delivered support/case."""

import math

import cadquery as cq
import pytest

from gripper_design.p05_cable_clearance import (
    DEFAULT_SOURCE,
    WindowSpec,
    candidate,
    change_mask,
    nominal_plug_corridors,
    seat_preservation,
)
from gripper_design.p05_cable_relief import diagnostic_wires, protected
from scripts.assembly_io import bounds, read_step


@pytest.fixture(scope="module")
def geometry():
    rows = read_step(DEFAULT_SOURCE)[2]
    source = next(r.world for r in rows if r.name == "ARM_P05_wrist_XL430")
    cases = [r.world for r in rows if r.name == "PG3_XL430_fixed"]
    assert len(cases) == 2
    return source, candidate(source, cases), cases


def solid_volume(shape):
    return sum(abs(s.Volume()) for s in shape.Solids())


def test_exported_v2_support_keeps_holes_bridge_and_material_outside_mask(geometry):
    old, new, _ = geometry
    removed = old.cut(new)
    assert new.isValid() and len(new.Solids()) == 1
    assert 250 < solid_volume(removed) < 300
    assert solid_volume(new.cut(old)) < 1e-4
    assert solid_volume(removed.cut(change_mask())) < 1e-4
    assert solid_volume(removed.intersect(protected())) < 1e-4
    for shape in (old, new):
        assert solid_volume(shape.cut(shape.copy())) < 1e-4
        assert solid_volume(shape.intersect(shape.copy())) == pytest.approx(
            solid_volume(shape), abs=1e-4
        )


def test_actual_opposed_case_seats_are_preserved_as_material_sets(geometry):
    old, new, cases = geometry
    rows = seat_preservation(old, new, cases)
    assert len(rows) == 2
    for row in rows:
        assert row["before_mm2"] == pytest.approx(942.0050459, abs=1e-4)
        assert row["lost_mm2"] < 1e-4
        assert row["added_mm2"] < 1e-4
        assert row["normal_dot"] == pytest.approx(-1, abs=1e-6)
        assert row["passed"]


def test_simple_large_slot_is_rejected_for_removing_actual_case_seats(geometry):
    old, _, cases = geometry
    # This is the rejected 6x12 mm physical fixture, not a synthetic error.
    enlarged = old.cut(change_mask(WindowSpec(width_mm=6, height_mm=12)))
    assert any(r["lost_mm2"] > 1 for r in seat_preservation(old, enlarged, cases))
    with pytest.raises(ValueError, match="case seating"):
        candidate(old, cases, WindowSpec(width_mm=6, height_mm=12))


def test_nominal_plug_can_cross_only_the_support_window_before_motor_installation(geometry):
    old, new, _ = geometry
    for plug in nominal_plug_corridors().values():
        assert solid_volume(old.intersect(plug)) > 1
        assert new.distance(plug) == pytest.approx(0.35, abs=1e-6)
        assert solid_volume(new.intersect(plug)) < 1e-4
        assert solid_volume(new.intersect(plug.translate((0, 2, 0)))) > 1


def test_six_assumed_wires_get_more_sidewall_clearance_only(geometry):
    _, new, _ = geometry
    for wire in diagnostic_wires().values():
        assert new.distance(wire) == pytest.approx(1.65, abs=1e-6)


def test_existing_hole_cylinder_faces_are_not_cut(geometry):
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    def holes(shape):
        return sorted(
            (tuple(round(v, 6) for v in bounds(f)), round(f.Area(), 6))
            for f in shape.Faces()
            if f.geomType() == "CYLINDER"
            and any(
                abs(BRepAdaptor_Surface(f.wrapped).Cylinder().Radius() - r) < 1e-6
                for r in (1.2, 5.5)
            )
        )

    old, new, _ = geometry
    assert len(holes(old)) == 18
    assert holes(new) == holes(old)


def test_oversized_mask_cannot_enter_screw_neighbourhood(geometry):
    old, _, cases = geometry
    with pytest.raises(ValueError, match="protected"):
        candidate(old, cases, WindowSpec(width_mm=25, height_mm=30, centre_y_mm=158.9))


@pytest.mark.parametrize("bad", [math.nan, math.inf, -1, 0])
def test_bad_dimensions_are_rejected(bad):
    with pytest.raises(ValueError):
        change_mask(WindowSpec(width_mm=bad))


def test_saved_support_roundtrip_controls_and_local_equivalence(geometry, tmp_path):
    _, new, cases = geometry
    path = tmp_path / "P05.step"
    cq.exporters.export(new, str(path))
    saved = cq.importers.importStep(str(path)).val()
    assert saved.isValid() and len(saved.Solids()) == 1
    assert solid_volume(saved.cut(saved.copy())) < 1e-4
    assert solid_volume(saved.intersect(saved.copy())) == pytest.approx(
        solid_volume(saved), abs=1e-4
    )
    assert solid_volume(saved.cut(new)) + solid_volume(new.cut(saved)) < 1e-4
    assert all(r["passed"] for r in seat_preservation(new, saved, cases))


def test_altered_input_is_rejected_before_outputs_are_created(tmp_path):
    from scripts.review_p05_cable_clearance import run

    bad_source = tmp_path / "changed.step"
    bad_source.write_text("Not the frozen Onshape V2")
    out = tmp_path / "outputs"
    with pytest.raises(ValueError, match="source SHA"):
        run(bad_source, out)
    assert not out.exists()


def test_export_checker_rejects_actual_placement_and_owner_changes():
    from types import SimpleNamespace

    from scripts.review_p05_cable_clearance import verify_occurrences

    old = SimpleNamespace(index=0, path="/arm/P05", name="P05", loc=cq.Location())
    renamed = SimpleNamespace(index=0, path="/arm/P05", name="131", loc=cq.Location())
    shifted = SimpleNamespace(index=0, path="/arm/P05", name="P05", loc=cq.Location((0.1, 0, 0)))
    with pytest.raises(ValueError, match="identities"):
        verify_occurrences([old], [renamed])
    with pytest.raises(ValueError, match="placements"):
        verify_occurrences([old], [shifted])
