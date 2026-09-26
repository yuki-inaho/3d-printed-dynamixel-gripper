import json

import cadquery as cq
import pytest

from study import OUT
from validate_geometry import newly_worse, pair
from scripts.assembly_io import read_step
from scripts.validate_camera_overhead_r4 import controls


def test_material_controls():
    assert all(r['passed'] for r in controls())


def test_gap_worsening_not_hidden():
    old=[{'a':'finger','b':'other','status':'FAIL','intersection_mm3':0,'gap_mm':.2}]
    new=[old[0]|{'gap_mm':.05}]
    assert newly_worse(old,new)


def test_boolean_exception_is_error():
    solid=cq.Solid.makeBox(10,10,10)
    class ErrorShape:
        def __getattr__(self,name):
            return getattr(solid,name)
        def intersect(self,other):
            raise RuntimeError('deliberate kernel evaluation failure')
    result=pair(ErrorShape(),solid)
    assert result['status']=='ERROR'
    assert 'deliberate' in result['error']


def test_surface_overlap_is_unknown():
    face=cq.Face.makePlane(5,5,cq.Vector(2,2,2),cq.Vector(0,0,1))
    solid=cq.Solid.makeBox(10,10,10)
    assert pair(face,solid)['status']=='UNKNOWN'


def test_actual_displaced_camera_rejected():
    parts={r.name:r.world for r in read_step(OUT/'CAD/Robot_250g_low_profile_D405.step')[2]}
    base=parts['CAM5_BASE']
    camera=parts['CAM5_D405_BODY']
    bad=camera.translate(base.Center()-camera.Center())
    result=pair(base,bad)
    assert result['status']=='FAIL'
    assert result['intersection_mm3']>1


def test_saved_comparison_has_no_hidden_worsening():
    data=json.loads((OUT/'reports/geometry-validation.json').read_text())
    assert len(data['cases'])==23
    for row in data['cases']:
        assert newly_worse(row['baseline']['nonpass'],row['candidate']['nonpass'])==[]


def test_saved_staged_tools_and_full_assembly_failure():
    data=json.loads((OUT/'reports/service-validation.json').read_text())
    assert len(data['checks'])==12
    assert data['all_staged_envelopes_pass']
    blocked={r['target'] for r in data['checks'] if r['installed_nonpass']}
    assert blocked=={f'CAM5_BASE_TAP_{i}' for i in range(4)}
    assert data['d405_stack']['insertion_mm']==pytest.approx(3)
