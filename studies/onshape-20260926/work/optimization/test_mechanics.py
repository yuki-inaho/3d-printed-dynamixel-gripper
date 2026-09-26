import numpy as np
import pytest
from mechanics import beam, depth_ok, moment, orient, project_points


def test_payload_250g_300mm():
    assert np.allclose(moment([[0, 300, 0]], [0.25]), [-0.73549875, 0, 0])


def test_vertical_base_axis_has_zero_gravity_torque():
    m = moment([[80, 300, 160]], [0.25])
    assert m[2] == 0
    assert np.linalg.norm(m[:2]) > 0.735


def test_reference_translation_and_mass_sum():
    assert np.allclose(
        moment([[0, 200, 0], [0, 400, 0]], [0.1, 0.1], [0, 100, 0]), [-0.392266, 0, 0]
    )


def test_orientation_is_right_handed():
    r, u, d = orient([0, 1, -1])
    assert np.allclose(np.cross(d, u), r)
    assert np.allclose(np.stack([r, u, -d]) @ np.stack([r, u, -d]).T, np.eye(3))


@pytest.mark.parametrize(
    "depth,small,large",
    [(69.9, False, False), (70, True, False), (99.9, True, False), (100, True, True)],
)
def test_minz_resolution_boundaries(depth, small, large):
    assert depth_ok(depth, "848x480") == small
    assert depth_ok(depth, "1280x720") == large


def test_projection_positive_negative_control():
    inside, depths = project_points(
        [[0, 100, 0], [200, 100, 0], [0, -10, 0]], [0, 0, 0], [0, 1, 0], [0, 0, 1]
    )
    assert inside.tolist() == [True, False, False]
    assert depths.tolist() == [100, 100, -10]


def test_beam_units_and_cubic_length_scaling():
    # F=1 N, L=100 mm, E=1000 N/mm², rectangle b=10 h=10 => I=833.333 mm⁴.
    stress, delta = beam(1, 100, 10, 10, 1000)
    assert stress == pytest.approx(0.6)
    assert delta == pytest.approx(0.4)
    assert beam(1, 50, 10, 10, 1000)[1] == pytest.approx(0.05)
