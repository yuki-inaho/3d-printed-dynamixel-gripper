"""Rendered known occlusion controls; this is not a real-camera calibration."""
import numpy as np

from gripper_design.camera_overhead_r4 import box
from scripts.camera_view_r4 import View


def measure(blocker):
    parts={'TARGET':box(-1,1,-1,1,0,1)}
    if blocker is not None:parts['BLOCKER']=blocker
    v=View(parts,(0,0,10),(0,0,-1),(0,1,0),60,size=(200,150))
    try:
        visible=v.capture(seg=True);reference=v.capture(seg=True,only={'TARGET'})
        mask=reference==v.ids['TARGET']; assert mask.sum()>100
        return np.sum((visible==v.ids['TARGET'])&mask)/mask.sum()
    finally:v.close()


def test_reference_full_and_total_occlusion():
    assert measure(None)>.99
    assert measure(box(-3,3,-3,3,3,4))==0


def test_partial_occlusion_not_counted_as_full():
    ratio=measure(box(-3,0,-3,3,3,4))
    assert .3<ratio<.7
