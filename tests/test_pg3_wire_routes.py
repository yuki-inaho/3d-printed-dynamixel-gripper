import math

import pytest

from scripts.probe_pg3_wire_routes import quarter_route


def test_quarter_route_volume_and_curvature_contract():
    shape, info = quarter_route((0, 10, 5), 1, 3, 4, 0, 1, 12)
    assert shape.isValid() and len(shape.Solids()) == 1
    assert info["minimum_centreline_radius_mm"] == 3
    assert info["start_tangent"] == [0, -1, 0]
    expected_length = 3 + math.pi * 3 / 2 + 9
    assert shape.Volume() == pytest.approx(math.pi * 0.5**2 * expected_length, abs=1e-5)


def test_routes_detect_wire_overlap_not_only_arm_overlap():
    a, _ = quarter_route((0, 10, 5), 1, 3, 4, 2, -1, -10)
    b, _ = quarter_route((0, 10, 7.5), 1, 3, 4, 2, -1, -10)
    assert a.intersect(b).Volume() > 5
    c, _ = quarter_route((0, 10, 7.5), 1, 3, 4, 0, 1, 12)
    d, _ = quarter_route((0, 10, 5), 1, 3, 4, 0, 1, 12)
    assert c.distance(d) == pytest.approx(1.5)


@pytest.mark.parametrize("radius,end_y", [(0.4, 4), (3, 9), (float("nan"), 4)])
def test_rejects_impossible_or_unbounded_route(radius, end_y):
    with pytest.raises(ValueError):
        quarter_route((0, 10, 5), 1, radius, end_y, 0, 1, 12)


def test_terminal_positions_are_not_header_bbox_centres():
    from gripper_design.build import _source_rows
    from scripts.probe_pg3_wire_routes import terminal_centres

    shapes = {r.name: r.world for r in _source_rows()}
    for name, x in (("M05_ref03", 9.95), ("M05_ref04", -10.35)):
        points, pcb = terminal_centres(shapes[name])
        assert pcb == pytest.approx(161.1)
        assert [p[0] for p in points] == pytest.approx([x] * 3)
        assert [p[2] for p in points] == pytest.approx([176.2, 178.7, 181.2])


def test_terminal_extraction_rejects_box_proxy():
    import cadquery as cq

    from scripts.probe_pg3_wire_routes import terminal_centres

    with pytest.raises(ValueError, match="unexpected terminal"):
        terminal_centres(cq.Solid.makeBox(3.8, 9.2, 10))
