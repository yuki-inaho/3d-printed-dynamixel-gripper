"""Negative controls for the provisional ID5 camera sightline model."""

from types import SimpleNamespace

import pytest

from camera_jig.id5_corner_vision import (
    camera_axes,
    cube_fits_between_pads,
    frame_bounds,
    segment_hits_box,
)


def test_horizontal_or_backwards_camera_is_rejected():
    with pytest.raises(ValueError, match="forward and downward"):
        camera_axes((0, 0, 10), (0, 10, 10))
    with pytest.raises(ValueError, match="forward and downward"):
        camera_axes((0, 0, 10), (0, -10, 0))


def test_assumed_fov_changes_projected_acceptance():
    pad = SimpleNamespace(xmin=-25, xmax=25, ymin=204, ymax=224, zmin=150, zmax=179)
    origin = (0, 178, 226)
    target = (0, 214.6, 164.6)

    wide = frame_bounds(origin, target, pad, fov_y_deg=50)
    narrow = frame_bounds(origin, target, pad, fov_y_deg=15)

    assert max(abs(value) for value in wide) < 1
    assert max(abs(value) for value in narrow) > 1


def test_frame_aabb_hit_is_not_silently_discarded():
    frame = SimpleNamespace(xmin=-46, xmax=46, ymin=182, ymax=189, zmin=137, zmax=193)

    assert segment_hits_box((0, 170, 220), (0, 205, 150), frame)
    assert not segment_hits_box((0, 178, 226), (0, 205, 150), frame)


def test_diagnostic_cube_is_not_shown_in_a_closed_gap():
    closed_left = SimpleNamespace(xmax=-0.66)
    closed_right = SimpleNamespace(xmin=0.26)
    open_left = SimpleNamespace(xmax=-24.65)
    open_right = SimpleNamespace(xmin=24.25)

    assert not cube_fits_between_pads(closed_left, closed_right, -0.2, 10)
    assert cube_fits_between_pads(open_left, open_right, -0.2, 30)
