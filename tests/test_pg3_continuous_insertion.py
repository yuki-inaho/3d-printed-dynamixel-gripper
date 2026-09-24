import cadquery as cq
import pytest

from scripts.certify_pg3_insertion import certify_pair, translation_cover


def test_continuous_cover_detects_thin_between_sample_obstacle():
    mover = cq.Solid.makeBox(0.1, 1, 1)
    thin = cq.Solid.makeBox(0.01, 1, 1, (0.45, 0, 0))
    assert mover.intersect(thin).Volume() == 0
    assert mover.translate((1, 0, 0)).intersect(thin).Volume() == 0
    assert certify_pair(mover, thin, (1, 0, 0))["status"] == "UNPROVEN"
    assert certify_pair(mover, thin.translate((0, 2, 0)), (1, 0, 0))["status"] == "PROVEN_CLEAR"


def test_continuous_cover_includes_start_interior_and_rejects_surfaces():
    mover = cq.Solid.makeBox(10, 10, 10)
    interior = cq.Solid.makeBox(1, 1, 1, (4, 4, 4))
    assert certify_pair(mover, interior, (1, 0, 0))["status"] == "UNPROVEN"
    with pytest.raises(ValueError):
        translation_cover(mover.Faces()[0], (1, 0, 0))
