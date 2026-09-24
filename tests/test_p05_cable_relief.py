import cadquery as cq
import pytest

from gripper_design.p05_cable_relief import (
    candidate,
    change_mask,
    diagnostic_wires,
    original,
    protected,
)


@pytest.fixture(scope="module")
def geometry():
    return original(), candidate(), diagnostic_wires()


def test_original_obstructs_six_complete_sidewall_exits(geometry):
    old, _, wires = geometry
    assert len(wires) == 6
    for wire in wires.values():
        assert old.intersect(wire).Volume() == pytest.approx(11.34114948, abs=1e-5)


def test_candidate_clears_only_the_assumed_wire_sidewall_passage(geometry):
    _, new, wires = geometry
    assert new.isValid() and len(new.Solids()) == 1
    assert new.Volume() > 0
    for wire in wires.values():
        assert sum(abs(s.Volume()) for s in new.intersect(wire).Solids()) < 1e-4


def test_change_is_subtractive_and_confined_to_declared_mask(geometry):
    old, new, _ = geometry
    removed = old.cut(new)
    assert 170 < removed.Volume() < 180
    assert new.cut(old).Volume() < 1e-4
    assert removed.cut(change_mask()).Volume() < 1e-4
    assert removed.intersect(protected()).Volume() < 1e-4
    assert new.cut(new.copy()).Volume() < 1e-4
    assert new.intersect(new.copy()).Volume() == pytest.approx(new.Volume(), abs=1e-4)


def test_hole_seat_violating_mask_is_not_accepted(monkeypatch):
    import gripper_design.p05_cable_relief as design

    # Existing M05 case mounting axis, not an invented off-part control.
    breach = cq.Solid.makeCylinder(3.7, 6, (13.05, 158.9, 168.6), (1, 0, 0))
    assert original().intersect(breach).intersect(protected()).Volume() > 1
    monkeypatch.setattr(design, "change_mask", lambda: breach)
    with pytest.raises(ValueError, match="protected"):
        design.candidate()


def test_displaced_wire_is_not_a_false_clearance_pass(geometry):
    _, new, wires = geometry
    for wire in wires.values():
        assert new.intersect(wire.translate((0, 2, 0))).Volume() > 1


def test_assumed_routes_clear_unmodified_cover_with_quarter_mm_gap(geometry):
    from gripper_design.build import _source_rows
    from scripts.review_pg3 import inspect_pairs

    _, _, wires = geometry
    cover = next(r.world for r in _source_rows() if r.name == "M05_ref06")
    checked = inspect_pairs(wires | {"cover": cover}, [(n, "cover") for n in wires])
    assert checked["counts"] == {"PASS": 6}
    assert min(r["distance_mm"] for r in checked["pairs"]) == pytest.approx(0.25, abs=1e-6)


def test_previous_exit_position_is_still_rejected():
    from gripper_design.build import _source_rows
    from scripts.review_pg3 import inspect_pairs

    old_wires = diagnostic_wires(exit_y=150.6)
    cover = next(r.world for r in _source_rows() if r.name == "M05_ref06")
    checked = inspect_pairs(old_wires | {"cover": cover}, [(n, "cover") for n in old_wires])
    assert checked["counts"] == {"FAIL": 6}
    assert min(r["volume_mm3"] for r in checked["pairs"]) > 0.11


def test_wire_mutual_clearance_is_not_skipped(geometry):
    from itertools import combinations

    from scripts.review_pg3 import inspect_pairs

    wires = geometry[2]
    assert inspect_pairs(wires, list(combinations(wires, 2)))["counts"] == {"PASS": 15}


def test_original_cylindrical_hole_faces_are_preserved(geometry):
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    from scripts.assembly_io import bounds

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
