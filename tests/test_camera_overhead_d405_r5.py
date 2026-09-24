"""R5 D405 contracts measured from generated B-rep, not from the Spec alone."""
import math
from dataclasses import replace

import numpy as np
import pytest
from OCP.BRepAdaptor import BRepAdaptor_Surface

from gripper_design.camera_overhead_d405_r5 import (
    D405,
    ROBONINE_PITCH_DEG,
    Spec,
    basis,
    build,
    cheek_profile,
    d405_carrier_local,
    d405_stack,
    imagers,
    local_point,
    optical_direction,
    usb_plug_local,
    validate_spec,
    world_to_local,
)
from gripper_design.camera_overhead_r4 import box
from scripts.validate_camera_overhead_d405_r5 import declared_contact, internal_pair
from scripts.validate_camera_overhead_r4 import pair


def _through_axes(shape, radius):
    """Centres of cylinder faces of the given radius with axis along local Z."""
    out = []
    for f in shape.Faces():
        if f.geomType() != 'CYLINDER':
            continue
        c = BRepAdaptor_Surface(f.wrapped).Cylinder()
        d = c.Axis().Direction()
        if abs(c.Radius() - radius) < 1e-6 and abs(d.Z()) > .999:
            p = c.Location()
            out.append((round(p.X(), 4), round(p.Y(), 4)))
    return sorted(set(out))


def test_nominal_spec_and_d405_stack():
    s = Spec()
    validate_spec(s)
    st = d405_stack(s)
    assert st['insertion_mm'] == pytest.approx(3.0)
    assert st['insertion_mm'] <= D405['rear_m3_max_insert_mm'] - .5
    assert st['thread_engagement_verified_on_hardware'] is False


@pytest.mark.parametrize('change', [
    {'pitch_deg': 62.0}, {'pitch_deg': float('nan')}, {'pitch_deg': 25.0}, {'pitch_deg': 85.0},
    {'motor': 'XL330'}, {'parent': 'output_horn'}, {'extra_motor_count': 1},
    {'cheek_inner_x': 21.5}, {'cheek_attach_v': (-27.0, -5.0)},
    {'d405_screw_length': 8.0}, {'d405_screw_length': 4.0},
    {'glass_center': (0.0, float('inf'), 250.0)}, {'base_screw_length': 10.0},
])
def test_bad_spec_rejected(change):
    with pytest.raises(ValueError):
        validate_spec(replace(Spec(), **change))


def test_carrier_has_measured_d405_20mm_slots_and_uvc_28mm_holes():
    plate = d405_carrier_local(Spec())
    # Slot ends are half-cylinders of the M3 clearance radius, 1 mm above/below the nominal axis.
    ends = _through_axes(plate, 1.7)
    d405 = [p for p in ends if abs(abs(p[0]) - 10) < 1e-6]
    assert sorted(d405) == [(-10, -1), (-10, 1), (10, -1), (10, 1)]
    uvc = _through_axes(plate, 1.2)
    assert uvc == [(-14, -14), (-14, 14), (14, -14), (14, 14)]
    ties = [p for p in ends if abs(abs(p[0]) - Spec().tie_bolt_local[0]) < 1e-6]
    assert len(ties) == 2


def test_optical_axis_is_measured_pitch_below_approach_axis():
    s = Spec()
    d = optical_direction(s)
    approach = np.array((0, 1, 0))
    angle = math.degrees(math.acos(float(d @ approach)))
    assert angle == pytest.approx(65.0)
    assert d[2] < 0  # looks down
    assert s.pitch_deg % 5 == 0
    assert ROBONINE_PITCH_DEG == 30.0


def test_imagers_straddle_the_axis_by_datasheet_baseline():
    im = imagers(Spec())
    assert np.linalg.norm(im['right'] - im['left']) == pytest.approx(D405['baseline_mm'])
    assert im['left'][0] < im['right'][0]


def test_plate_face_carries_the_d405_rear_face():
    s = Spec()
    p = build(s)
    body = p['CAM5_D405_BODY']
    plate = p['CAM5_D405_CARRIER']
    assert abs(body.intersect(plate).Volume()) < 1e-5
    assert body.distance(plate) < 1e-6
    # The glass centre sits 23 mm along the optical axis from the plate face.
    rear = local_point((0, 0, 0), s)
    assert np.linalg.norm(np.array(s.glass_center) - rear) == pytest.approx(23.0)


def test_usb_band_clears_cheek_attachment():
    s = Spec()
    plug = usb_plug_local(s)
    bb = plug.BoundingBox()
    assert bb.ymin > s.cheek_attach_v[1]
    # Cheek top edge stays below the plug band over the plug depth.
    _, (y1, z1), (yb, zb), _ = cheek_profile(s)
    lb = world_to_local((-0.2, y1, z1), s)
    tb = world_to_local((-0.2, yb, zb), s)
    for z in np.linspace(bb.zmin, bb.zmax, 5):
        t = (z - tb[2]) / (lb[2] - tb[2])
        v = tb[1] + t * (lb[1] - tb[1])
        assert v < bb.ymin - 3.0


def test_screw_thread_roi_accepts_engagement_and_rejects_body_clash():
    s = Spec()
    p = build(s)
    ok = internal_pair('CAM5_D405_SCREW_0', p['CAM5_D405_SCREW_0'], 'CAM5_D405_BODY',
                       p['CAM5_D405_BODY'], s)
    assert ok['status'] == 'PASS'
    moved = p['CAM5_D405_SCREW_0'].translate(tuple(basis(s.pitch_deg)[0] * 3.0))
    bad = internal_pair('CAM5_D405_SCREW_0', moved, 'CAM5_D405_BODY', p['CAM5_D405_BODY'], s)
    assert bad['status'] == 'FAIL'


def test_undeclared_contacts_still_fail():
    assert declared_contact('CAM5_D405_CARRIER', 'CAM5_BASE')
    assert not declared_contact('CAM5_D405_BODY', 'CAM5_BASE')
    assert not declared_contact('CAM5_D405_USB_PLUG', 'CAM5_BASE')
    a = box(0, 1, 0, 1, 0, 1)
    assert pair(a, a.translate((.5, 0, 0)), contact=True)['status'] == 'FAIL'


def test_all_new_parts_are_single_valid_solids():
    for name, shape in build().items():
        assert shape.isValid(), name
        assert len(shape.Solids()) == 1, name
        assert shape.Volume() > 0, name
