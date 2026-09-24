"""Positive geometry gates and negative controls for camera-gripper revision."""
import copy
import json
import math
from pathlib import Path

import cadquery as cq
import numpy as np
import pytest
import vtk

from design import (build, load_config, make_parts, volume, MOUNT_POINTS, PIVOT,
                    MOUNT_CENTER, camera_basis, camera_optical_center, DEFAULT_OUT)
from review import (bijective_match, cylinder_axes, empty_cylindrical_path,
                    matrix, fabrication_gate, reload_items, check_interfaces,
                    continuous_mount_bound, preservation, check_parts, scan)
from vision import (project, polydata, combine, visible_samples, turn_vertices)

@pytest.fixture(scope='module')
def design():return build()

@pytest.fixture(scope='module')
def loaded(design):
    if not (DEFAULT_OUT/'CAD/full_arm_0deg.step').exists():pytest.fail('Build the prototype before running its integration tests')
    return reload_items(DEFAULT_OUT/'CAD/full_arm_0deg.step',design.items)

@pytest.mark.parametrize('field,value',[
    ('clocking_deg',0),('flange_thickness_mm',5),('opening_max_deg',51),
    ('assumed_hfov_deg',0),('assumed_vfov_deg',180),('camera_tilt_down_deg',0),
    ('camera_hole_pitch_mm',24),('carrier_thickness_mm',4),('pcb_spacer_mm',2),
    ('vision_sample_step_deg',8),('camera_carrier_origin_mm',[1,2,float('nan')]),
    ('camera_carrier_origin_mm',[1,2])])
def test_unsupported_configuration_fails(field,value,tmp_path):
    c=load_config();c[field]=value;p=tmp_path/'bad.json';p.write_text(json.dumps(c))
    with pytest.raises(ValueError):load_config(p)

def test_default_config():
    assert load_config()['baseline']=='follower_geometry_revision_mixed_servos'

def test_bijective_pattern_passes_permutation():
    assert bijective_match(MOUNT_POINTS,MOUNT_POINTS[[2,0,3,1]])['passed']

def test_bijective_pattern_rejects_duplicate():
    points=MOUNT_POINTS.copy();points[3]=points[2]
    assert not bijective_match(MOUNT_POINTS,points)['passed']

def test_bijective_pattern_rejects_missing():
    assert not bijective_match(MOUNT_POINTS,MOUNT_POINTS[:3])['passed']

def test_bijective_pattern_rejects_shifted():
    assert not bijective_match(MOUNT_POINTS,MOUNT_POINTS+[.1,0,0])['passed']

def test_original_breps_reused(design):
    assert all(i.shape.wrapped.IsSame(design.baseline.revised_shapes[int(i.key.split('_')[1])].wrapped)
               for i in design.items if i.key.startswith('original_'))

def test_upstream_placements_unchanged(design):
    for i in design.items:
        if i.role=='upstream':
            assert np.max(abs(matrix(i.loc)-matrix(design.baseline.revised_locations[int(i.key.split('_')[1])])) )<1e-10

def test_rigid_90_clocking_and_4mm_translation(design):
    relative=matrix(design.static_source_location.inverse*design.hand_world)
    assert np.allclose(relative[:3,:3],[[0,0,1],[0,1,0],[-1,0,0]],atol=1e-10)
    old=np.r_[MOUNT_CENTER,1];new=relative@old
    assert np.allclose(new[:3]-MOUNT_CENTER,[0,4,0],atol=1e-10)
    assert np.linalg.det(relative[:3,:3])==pytest.approx(1)

@pytest.mark.parametrize('key',['wrist_camera_bridge','uvc28_camera_carrier','uvc28_pcb_spacer_4mm'])
def test_new_parts_single_solid(design,key):
    assert design.parts[key].isValid() and len(design.parts[key].Solids())==1

def test_carrier_does_not_intersect_bridge(design):
    assert volume(design.parts['wrist_camera_bridge'].intersect(design.parts['uvc28_camera_carrier']))<1e-4

def test_bridge_preserves_complete_four_hole_flange(design):
    bridge=design.parts['wrist_camera_bridge'];centres=MOUNT_POINTS.copy();centres[:,1]=0
    assert bijective_match(centres,cylinder_axes(bridge,[0,1,0],1.15))['passed']
    for p in MOUNT_POINTS:
        assert empty_cylindrical_path(bridge,[p[0],-23.99,p[2]],[0,1,0],1.14,3.98)
    # Protect against mistakenly clipping off the entire wrist flange.
    assert bridge.isInside(cq.Vector(MOUNT_CENTER[0]+9,-22,MOUNT_CENTER[2]))

@pytest.mark.parametrize('angle',[-1,51,float('nan')])
def test_unreviewed_opening_rejected(design,angle):
    with pytest.raises(ValueError):design.at_opening(angle)

def test_camera_basis():
    r,u,f=camera_basis(load_config())
    assert np.allclose(r,[1,0,0]) and np.allclose(np.cross(r,-u),f)
    assert np.dot(f,u)==pytest.approx(0,abs=1e-12)

def test_optical_centre_projects_to_centre():
    c=load_config();r,u,f=camera_basis(c);lens=camera_optical_center(c)
    ndc,depth=project(np.array([lens+40*f]),c)
    assert np.allclose(ndc,[0,0]) and depth[0]==pytest.approx(40)

def test_narrow_fov_is_not_silently_relaxed():
    c=load_config();r,u,f=camera_basis(c);lens=camera_optical_center(c)
    c['assumed_hfov_deg']=5
    xy,_=project(np.array([lens+40*f+10*r]),c)
    assert abs(xy[0,0])>1


def fixture_visibility(blocked):
    c=load_config();r,u,f=camera_basis(c);lens=camera_optical_center(c)
    verts=np.array([lens+40*f+a*r+b*u for a,b in [(-5,-5),(5,-5),(5,5),(-5,5)]])
    faces=np.array([[0,1,2],[0,2,3]])
    meshes=[(verts,faces)]
    if blocked:meshes.append((verts-20*f,faces))
    vv,ff=combine(meshes);loc=vtk.vtkStaticCellLocator();loc.SetDataSet(polydata(vv,ff));loc.BuildLocator()
    points=np.array([lens+40*f+a*r+b*u for a in [-2,0,2] for b in [-2,0,2]])
    return visible_samples(points,np.tile(-f,(9,1)),verts,c,loc)

def test_first_hit_visible_surface():
    r=fixture_visibility(False);assert r['passed'] and r['visible_surface_witnesses']==9

def test_first_hit_blocks_occluded_surface():
    r=fixture_visibility(True);assert not r['passed'] and r['visible_surface_witnesses']==0

def test_jaw_opening_rotates_away_from_fixed_side():
    q=np.array([[PIVOT[0],PIVOT[1]+50,PIVOT[2]]]);p=turn_vertices(q,50)
    assert p[0,0]>q[0,0] and p[0,2]==pytest.approx(q[0,2])

def test_fabrication_gate_never_promotes_flags():
    assert not fabrication_gate(True, ['fake_signoff.pdf'])['accepted_for_fabrication']
    assert len(fabrication_gate(True)['blockers'])>=5

def test_collision_oracle_positive_and_negative_controls():
    from design import Item
    box=cq.Solid.makeBox(10,10,10)
    a=Item('a','a',box,cq.Location(),'a','camera_mount',(1,0,0))
    b=Item('b','b',box,cq.Location((5,0,0)),'b','camera_mount',(1,0,0))
    assert scan([a,b])['external_count']==1
    b.loc=cq.Location((11,0,0));assert scan([a,b])['passed_external']

def test_exported_identity_count(loaded,design):
    assert len(loaded)==len(design.items)==167
    assert sum(len(i.shape.Solids()) for i in loaded)==123

def test_reimport_preservation(loaded,design):
    assert preservation(design,loaded)['passed']

def test_reimport_interfaces(loaded,design):
    assert check_interfaces(design,loaded)['passed']

def test_continuous_new_mount_clearance(loaded,design):
    assert continuous_mount_bound(design,loaded)['passed']

def test_step_stl_parts(design):
    assert check_parts(DEFAULT_OUT,design)['passed']

def test_validation_report():
    p=DEFAULT_OUT/'reports/validation.json'
    assert p.exists(), 'Run build first'
    r=json.loads(p.read_text())
    assert r['geometry_passed'] and not r['fabrication_gate']['accepted_for_fabrication']
    assert len(r['vision']['angles'])==51 and len(r['jaw_motion']['angles'])==11
    assert r['closed_pose_collisions']['external_count']==0
    assert r['open_pose_collisions']['external_count']==0
