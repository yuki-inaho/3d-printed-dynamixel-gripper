import math

import cadquery as cq
import pytest

from gripper_design.pg3 import PG3Model, position_mm, to_arm
from gripper_design.pg3_installation import frame_candidate, installed_assembly
from scripts.review_pg3_motion_clearance import DistanceTo, certify_interval, point_speed_bound


@pytest.fixture(scope="module")
def model():
    return PG3Model()


def test_opening_frame_end_has_running_gap(model):
    original = model.neutral["frame"]
    updated = frame_candidate(original)
    for angle in (25, 31.875):
        for side in ("L", "R"):
            carriage = model.at(angle)["carriage_" + side]
            assert original.distance(carriage) < 1e-6
            assert updated.distance(carriage) >= 0.3 - 1e-6


def test_frame_relief_preserves_material_outside_four_strips(model):
    from gripper_design.pg3_installation import frame_change_mask

    original = model.neutral["frame"]
    updated = frame_candidate(original)
    assert updated.isValid() and len(updated.Solids()) == 1
    assert original.Volume() - updated.Volume() == pytest.approx(11.04, abs=1e-5)
    assert updated.cut(original).Volume() < 1e-5
    assert original.cut(updated).cut(frame_change_mask()).Volume() < 1e-5
    # Actual case and cap fastening regions are not in the relief masks.
    for x, y in ((-11, -8), (11, -8), (-37.5, -24.5), (-37.5, 24.5), (37.5, -24.5), (37.5, 24.5)):
        protected = cq.Solid.makeCylinder(3.5, 12, (x, y, 16))
        assert original.intersect(protected).cut(updated).Volume() < 1e-5
    # All four end lands retain 2 x 3.2 x 4.6 mm material; not a strength claim.
    for x in (-46, 44):
        for y in (-22, 18.8):
            retained = cq.Solid.makeBox(2, 3.2, 4.6, (x, y, 19.5))
            assert retained.cut(updated).Volume() < 1e-5


@pytest.mark.parametrize(("side", "sign"), [("L", -1), ("R", 1)])
def test_saved_frame_has_continuous_nominal_carriage_clearance(model, tmp_path, side, sign):
    # One side per test so parallel runs can certify L and R concurrently.
    path = tmp_path / "frame.step"
    cq.exporters.export(frame_candidate(model.neutral["frame"]), str(path))
    frame = cq.importers.importStep(str(path)).val()
    source = model.neutral["carriage_" + side]
    to_frame = DistanceTo(frame)  # same exact distance; the saved frame is loaded once

    def distance(angle):
        shift = sign * (position_mm(math.degrees(angle)) - position_mm(90))
        return to_frame(source.translate((shift, 0, 0)))

    result = certify_interval(
        distance, point_speed_bound(source, side), math.radians(25), math.radians(135)
    )
    assert result["status"] == "PROVEN_CLEAR", result


def test_installed_assembly_uses_relief_not_reference_frame(model):
    frame = installed_assembly(model, 90)["PG3_frame"]
    expected = to_arm(frame_candidate(model.neutral["frame"]))
    assert frame.Volume() == pytest.approx(expected.Volume(), abs=1e-5)
    assert frame.cut(expected).Volume() < 1e-5
    assert expected.cut(frame).Volume() < 1e-5
