"""Adversarial geometry checks, separate from configuration contracts."""
import cadquery as cq
import pytest

from gripper_design.camera_overhead_r4 import box, build, opening_mm
from scripts.service_camera_overhead_r4 import sweep, tool
from scripts.validate_camera_overhead_r4 import new_pair_contact, pair


def test_all_new_solids_and_self_copy_controls():
    p=build()
    for name,s in p.items():
        assert s.isValid(),name
        assert len(s.Solids())==1,name
        assert s.Volume()>0,name
        copy=s.copy()
        assert abs(s.intersect(copy).Volume()-s.Volume())<.01,name


def test_partial_overlap_and_containment_rejected():
    a=box(0,10,0,10,0,10)
    assert pair(a,box(2,3,2,3,2,3))['status']=='FAIL'
    assert pair(a,box(9,19,0,10,0,10))['status']=='FAIL'
    assert pair(a,box(10.2,20.2,0,10,0,10))['status']=='FAIL'


def test_surface_box_is_conservative_not_ignored():
    face=cq.Face.makePlane(10,10,cq.Vector(0,0,0),cq.Vector(1,1,1))
    a=box(30,31,30,31,30,31)
    assert pair(a,face)['status']=='PASS'
    # Inside the surface's enclosing box cannot be promoted to a PASS.
    assert pair(box(-.1,.1,-.1,.1,-.1,.1),face)['status']=='UNKNOWN'


def test_explicit_internal_camera_fit_still_rejects_interpenetration():
    assert new_pair_contact('CAM4_ASSUMED_PCB','CAM4_ASSUMED_USB_PLUG')
    assert not new_pair_contact('CAM4_ASSUMED_PCB','CAM4_BASE')
    a=box(0,1,0,1,0,1)
    assert pair(a,a.translate((.5,0,0)),contact=True)['status']=='FAIL'


def test_insert_path_detects_intermediate_obstacle():
    moving={'MOVING':box(0,1,0,1,0,1)}
    obs={'OBSTACLE':box(0,1,0,1,4,5)}
    r=sweep('negative',moving,obs,(0,0,1),8)
    assert not r['sampled_path_pass']
    assert r['failures']


def test_handle_collision_not_only_shaft():
    t=tool((0,0,0),(0,0,1))
    obstacle=box(5,6,0,1,40,41)
    assert pair(t,obstacle)['status']=='FAIL'


def test_invalid_angle_not_nan_propagation():
    from gripper_design.camera_overhead_r4 import retained_at
    # This fails closed even for empty inventory.
    with pytest.raises(ValueError):retained_at({},float('nan'))


def test_opposing_pad_opening_matches_analytical():
    assert opening_mm(25)>48
    assert .3<opening_mm(135)<1.5


def test_axial_tool_sweep_detects_obstacle_only_during_extraction():
    stationary=tool((0,0,0),(0,0,1))
    swept=tool((0,0,0),(0,0,1),travel=30)
    obstacle=box(5,6,0,1,78,79)
    assert pair(stationary,obstacle)['status']=='PASS'
    assert pair(swept,obstacle)['status']=='FAIL'


def test_interval_speed_bound_and_unknown_mechanism():
    import math

    from scripts.continuous_camera_clearance_r4 import group, speed_bound
    for t in [25,50,90,120,135]:
        h=1e-5
        derivative=(opening_mm(t+h)-opening_mm(t-h))/(2*h)*180/math.pi/2
        assert abs(derivative)<=speed_bound('R',[0]*6)
    with pytest.raises(ValueError):group('PG3_UNKNOWN_EXTRA_JOINT')


def test_nut_driver_requires_real_screw_tip_clearance():
    from gripper_design.camera_overhead_r4 import cylinder
    from scripts.service_camera_overhead_r4 import nut_driver_envelope
    protruding=cylinder(1,.45,(0,0,0))
    assert pair(tool((0,0,0),(0,0,1),shaft_d=7),protruding)['status']=='FAIL'
    assert pair(nut_driver_envelope((0,0,0),(0,0,1)),protruding)['status']=='PASS'
