import math

import cadquery as cq
import pytest
from design import (
    CUT_Y,
    extend_finger,
    extended_arm,
    load_source,
    payload_delta,
    preservation,
)


@pytest.fixture(scope="module")
def arm():
    return load_source()


@pytest.mark.parametrize("side", ["L", "R"])
@pytest.mark.parametrize("delta", [0, 5, 15, 30])
def test_extension_root_preserved(arm, side, delta):
    original = arm[f"PG3_finger_{side}"]
    new = extend_finger(original, delta)
    result = preservation(original, new, delta)
    assert result["pass"], result
    assert new.isValid() and len(new.Solids()) == 1
    assert new.Volume() >= original.Volume() - 1e-5


def test_extension_tip_and_pad_shift(arm):
    new = extended_arm(arm, 15)
    for side in ["L", "R"]:
        for role in ["finger", "pad"]:
            name = f"PG3_{role}_{side}"
            assert new[name].BoundingBox().ymax == pytest.approx(
                arm[name].BoundingBox().ymax + 15, abs=1e-6
            )
    for name in arm:
        if name not in {"PG3_finger_L", "PG3_finger_R", "PG3_pad_L", "PG3_pad_R"}:
            assert new[name] is arm[name]


def test_payload_delta():
    assert payload_delta(10) == pytest.approx(0.024516625, abs=1e-12)
    assert payload_delta(0) == 0
    with pytest.raises(ValueError):
        payload_delta(math.nan)
    with pytest.raises(ValueError):
        payload_delta(-1)


def test_disconnected_and_translated_bad_controls(arm):
    original = arm["PG3_finger_R"]
    assert not preservation(original, original.translate((0, 15, 0)), 15)["pass"]
    valid = extend_finger(original, 15)
    extra = cq.Solid.makeBox(1, 1, 1, cq.Vector(50, CUT_Y + 5, 200))
    broken = cq.Compound.makeCompound([valid, extra])
    assert not preservation(original, broken, 15)["pass"]
