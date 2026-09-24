import math
from itertools import pairwise

import numpy as np
import pytest

from gripper_design.parallel_jaw import (
    ParallelJawParameters,
    build_parallel_jaw,
    jaw_state,
    opening_mm,
    validate_parameters,
)


def test_parallel_jaw_orientation_error():
    parameters = ParallelJawParameters()
    for theta in np.linspace(parameters.theta_min_rad, parameters.theta_max_rad, 21):
        state = jaw_state(parameters, float(theta))
        assert state.left_face_normal == pytest.approx((1.0, 0.0, 0.0))
        assert state.right_face_normal == pytest.approx((-1.0, 0.0, 0.0))
        assert state.orientation_error_deg <= 0.1
        assert state.left_inner_x_mm == pytest.approx(-state.right_inner_x_mm)


def test_opening_mapping_monotonic():
    parameters = ParallelJawParameters()
    angles = np.linspace(parameters.theta_min_rad, parameters.theta_max_rad, 21)
    analytic = [opening_mm(parameters, float(theta)) for theta in angles]
    measured = [jaw_state(parameters, float(theta)).measured_opening_mm for theta in angles]
    assert all(b > a for a, b in pairwise(analytic))
    assert measured == pytest.approx(analytic, abs=0.05)


def test_invalid_parallel_jaw_parameters_are_rejected():
    with pytest.raises(ValueError, match="pitch radius"):
        validate_parameters(ParallelJawParameters(pinion_pitch_radius_mm=0))
    with pytest.raises(ValueError, match="opposed"):
        validate_parameters(ParallelJawParameters(left_rack_direction=1, right_rack_direction=1))
    with pytest.raises(ValueError, match="positive"):
        validate_parameters(ParallelJawParameters(base_opening_mm=1, theta_min_rad=-1))
    with pytest.raises(ValueError, match="hard-stop"):
        jaw_state(ParallelJawParameters(), theta_rad=0.51)


def test_parallel_jaw_build_is_valid_concept_geometry():
    parameters = ParallelJawParameters()
    shapes = build_parallel_jaw(parameters, theta_rad=0.0)
    assert {"base", "left_jaw", "right_jaw", "pinion", "opposite_support"} <= set(shapes)
    for shape in shapes.values():
        assert shape.isValid()
        assert len(shape.Solids()) == 1
        assert shape.Volume() > 0
    assert parameters.output_pitch_circle_diameter_mm == pytest.approx(16.0)
    assert math.isfinite(sum(shape.Volume() for shape in shapes.values()))
