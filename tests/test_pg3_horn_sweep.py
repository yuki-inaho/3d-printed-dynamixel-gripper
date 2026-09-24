import math

import cadquery as cq
import numpy as np
import pytest
from OCP.BRepAdaptor import BRepAdaptor_Curve

from gripper_design.build import _source_rows
from gripper_design.pg3 import PG3Model, to_arm
from gripper_design.rotational_envelopes import curve_radial_bound, rotational_cover
from scripts.review_pg3_horn_sweep import inspect_horn_sweep


def test_trimmed_arc_maximum_is_between_vertices():
    edge = cq.Edge.makeCircle(2, (0, 0, 0), (1, 0, 0), 0, 180)
    adaptor = BRepAdaptor_Curve(edge.wrapped)
    middle = (adaptor.FirstParameter() + adaptor.LastParameter()) / 2
    point = np.asarray(adaptor.Value(middle).Coord())
    target = -1.5 * point[1:]
    endpoints = [
        adaptor.Value(t).Coord()[1:] for t in (adaptor.FirstParameter(), adaptor.LastParameter())
    ]
    assert max(math.dist(p, target) for p in endpoints) < 4
    assert curve_radial_bound(edge, 0, target) == pytest.approx(5, abs=1e-10)


@pytest.fixture(scope="module")
def horn():
    return to_arm(PG3Model().neutral["XL430_horn"])


def test_actual_trimmed_notch_is_not_its_full_parent_circle(horn):
    edge = horn.Faces()[0].Edges()[0]
    circle = BRepAdaptor_Curve(edge.wrapped).Circle()
    centre = (234.9, 164.6)
    parent_bound = math.dist(circle.Location().Coord()[1:], centre) + circle.Radius()
    assert parent_bound > 13
    assert curve_radial_bound(edge, 0, centre) == pytest.approx(10.25, abs=1e-7)


def test_horn_sweep_bounds_every_face_without_trusting_bad_booleans(horn):
    _, report = rotational_cover(horn, 0, (234.9, 164.6), 10.3)
    assert report["source_face_count"] == len(report["faces"]) == len(horn.Faces())
    assert report["maximum_required_radius_mm"] == pytest.approx(10.2500001, abs=1e-7)
    assert not report["source_boolean_used_as_containment_proof"]


def test_undersized_and_displaced_horn_are_not_enclosed(horn):
    with pytest.raises(ValueError, match="exceeds"):
        rotational_cover(horn, 0, (234.9, 164.6), 10.0)
    with pytest.raises(ValueError, match="exceeds"):
        rotational_cover(horn.translate((0, 0.2, 0)), 0, (234.9, 164.6), 10.3)


def test_tilted_circular_edge_bound_is_still_conservative():
    edge = cq.Edge.makeCircle(2, (1, 3, 0), (1, 1, 1), 300, 420)
    adaptor = BRepAdaptor_Curve(edge.wrapped)
    result = curve_radial_bound(edge, 0, (0, 0))
    for t in np.linspace(adaptor.FirstParameter(), adaptor.LastParameter(), 100):
        p = adaptor.Value(t).Coord()
        assert math.hypot(p[1], p[2]) <= result + 1e-10


def test_complete_spacers_clear_but_inward_controls_penetrate(horn):
    spacers = {
        f"ARM_{r.name}": r.world for r in _source_rows() if r.name in ("M06_ref27", "M06_ref28")
    }
    result = inspect_horn_sweep(horn, spacers)
    assert len(result["accepted_clear_pairs"]) == 2
    assert result["negative_controls_detected"]
    assert result["envelope"]["source_face_count"] == len(result["envelope"]["faces"])
    assert all(r["continuous_distance_lower_bound_mm"] > 0.05 for r in result["pairs"])
    assert not result["installation_approved"]
