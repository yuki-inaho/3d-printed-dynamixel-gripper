"""Additional R4 contracts. Geometry and real hardware acceptance are separate."""
import math
from dataclasses import replace

import pytest

from gripper_design.camera_overhead_r4 import Spec, basis, screw_stack, validate_spec


def test_nominal_spec():
    validate_spec(Spec())


@pytest.mark.parametrize("change", [
    {"motor": "XL330"}, {"parent": "output_horn"},
    {"pitch_deg": -63.0}, {"pitch_deg": float("nan")},
    {"camera_pitch_mm": 27.0}, {"extra_motor_count": 1},
    {"base_seat_thickness": 0.0}, {"base_screw_length": 10.0},
    {"board_thickness": 5.0}, {"board_clearance": 0.0},
])
def test_bad_spec_rejected(change):
    with pytest.raises(ValueError):
        validate_spec(replace(Spec(), **change))


def test_nominal_stack():
    v=screw_stack(5,2,.5,4)
    assert v['penetration_mm']==pytest.approx(2.5)
    assert v['bottom_margin_mm']==pytest.approx(1.5)
    assert v['actual_thread_strength_verified'] is False


@pytest.mark.parametrize("length,thickness,washer",[(10,2,.5),(2,2,.5),(float('nan'),2,.5)])
def test_bad_stack_rejected(length,thickness,washer):
    with pytest.raises(ValueError): screw_stack(length,thickness,washer,4)


def test_camera_basis():
    _,v,n=basis(63)
    assert -n[2]<0
    assert math.fsum(a*b for a,b in zip(v,n))==pytest.approx(0,abs=1e-12)