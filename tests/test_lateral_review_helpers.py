import json

import cadquery as cq
import numpy as np
import pytest

from scripts.compare_lateral_wrist import bores
from scripts.review_lateral_delivery import common_volume, write_json


def test_intersection_positive_and_negative_controls():
    box = cq.Solid.makeBox(10, 10, 10)
    assert common_volume(box, box.translate((5, 0, 0))) == pytest.approx(500)
    assert common_volume(box, box.translate((11, 0, 0))) == pytest.approx(0)


def test_audit_serializes_numpy_and_rejects_nan(tmp_path):
    path = tmp_path / "check.json"
    write_json(path, {"ok": np.bool_(True), "values": np.array([1.0, 2.0])})
    assert json.loads(path.read_text()) == {"ok": True, "values": [1.0, 2.0]}
    with pytest.raises(ValueError):
        write_json(tmp_path / "bad.json", {"value": float("nan")})


def test_bores_are_concave_not_outer_cylinders():
    axis = np.array([0, 1, 0])
    center = np.zeros(3)
    plate = cq.Solid.makeCylinder(12, 4, cq.Vector(0, 0, 0), cq.Vector(*axis))
    for x, z in ((6, 0), (-6, 0), (0, 6), (0, -6)):
        plate = plate.cut(cq.Solid.makeCylinder(1.15, 6, cq.Vector(x, -1, z), cq.Vector(*axis)))
    records = bores(plate, 1.15, axis, center)
    assert len(records) == 4
    assert [r["radius_from_axis_mm"] for r in records] == pytest.approx([6] * 4)
    assert bores(plate, 12, axis, center) == []
