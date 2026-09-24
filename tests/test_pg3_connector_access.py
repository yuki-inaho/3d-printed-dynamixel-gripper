import cadquery as cq
import pytest

from gripper_design.build import _source_rows
from scripts.assembly_io import bounds
from scripts.probe_pg3_connector_access import corridors


@pytest.fixture
def headers():
    return {
        f"ARM_{r.name}": r.world
        for r in _source_rows()
        if r.name in ("M05_ref03", "M05_ref04", "M06_ref03", "M06_ref04")
    }


def test_nominal_corridor_and_original_link_obstruction(headers):
    paths, evidence = corridors(headers)
    assert len(paths) == 4
    link = next(r.world for r in _source_rows() if r.name == "P05_wrist_XL430")
    for index in (3, 4):
        path = paths[f"PORT_ACCESS_M05_{index}"]
        bb = bounds(path)
        assert (bb[1], bb[4]) == pytest.approx((107.9, 147.9))
        assert path.Volume() == pytest.approx(40 * 9.5 * 3.8)
        assert path.intersect(link).Volume() == pytest.approx(144.4, abs=1e-5)
    assert all(not r["mated_depth_or_cable_bend_confirmed"] for r in evidence.values())


def test_rejects_wrong_header_orientation(headers):
    headers["ARM_M05_ref03"] = cq.Solid.makeBox(9.2, 3.8, 10)
    with pytest.raises(ValueError, match="dimensions/orientation"):
        corridors(headers)


def test_rejects_axially_displaced_header_with_fixed_case_plane(headers):
    headers["ARM_M05_ref03"] = headers["ARM_M05_ref03"].translate((0, 10, 0))
    with pytest.raises(ValueError, match="pose"):
        corridors(headers)
