"""Independent checks of serialized prototype geometry; never a fabrication approval.

The exported STEP is re-imported before assembly, motion, and interface checks.
Supplier-internal intersections are reported separately, not called collision free.
"""
from __future__ import annotations
import itertools
import json
import math
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.TopAbs import TopAbs_REVERSED
from design import (Item, MOUNT_CENTER, MOUNT_POINTS, PIVOT, bounds, read_step,
                    volume, camera_basis, camera_point, rotate_about, DEFAULT_OUT)

EPS_VOLUME = 1e-4
EPS_LENGTH = 1e-5


def matrix(loc):
    t = loc.wrapped.Transformation()
    return np.array([[t.Value(r, c) for c in range(1, 5)] for r in range(1, 4)] + [[0, 0, 0, 1.]])


def reload_items(path: Path, expected: list[Item]) -> list[Item]:
    _, _, rows = read_step(path)
    got = {r.name: r for r in rows}
    want = {i.key: i for i in expected}
    if len(got) != len(rows) or set(got) != set(want):
        raise ValueError('STEP occurrence identity/count changed; cannot validate by display order')
    return [Item(k, want[k].original_path, got[k].shape, got[k].loc,
                 want[k].unit, want[k].role, want[k].color) for k in want]


def broad_pairs(items, moving_only=False):
    solid = [i for i in items if i.shape.Solids()]
    shapes = {i.key: i.world for i in solid}
    boxes = {k: np.array(bounds(s)) for k, s in shapes.items()}
    pairs = []
    for a, b in itertools.combinations(solid, 2):
        if moving_only and a.role != 'rotor' and b.role != 'rotor':
            continue
        ba, bb = boxes[a.key], boxes[b.key]
        if np.all(np.minimum(ba[3:], bb[3:]) - np.maximum(ba[:3], bb[:3]) > EPS_LENGTH):
            pairs.append((a, b))
    return solid, shapes, pairs


def scan(items, *, moving_only=False, include_internal=True):
    solid, shapes, pairs = broad_pairs(items, moving_only)
    if not include_internal:
        pairs = [(a, b) for a, b in pairs if a.unit != b.unit]
    hits, failures = [], []
    completed = 0
    for a, b in pairs:
        try:
            common = shapes[a.key].intersect(shapes[b.key])
            if common.Solids() and not common.isValid():
                raise ValueError('Invalid intersection result')
            v = volume(common)
            if not math.isfinite(v):
                raise ValueError('Nonfinite intersection volume')
            completed += 1
            if v > EPS_VOLUME:
                hits.append({'a': a.key, 'b': b.key, 'volume_mm3': v,
                             'supplier_internal': a.unit == b.unit,
                             'path_a': a.original_path, 'path_b': b.original_path})
        except Exception as exc:
            failures.append({'a': a.key, 'b': b.key, 'error': repr(exc)})
    external = [h for h in hits if not h['supplier_internal']]
    return {'solid_occurrences': len(solid), 'total_possible_pairs': len(solid)*(len(solid)-1)//2,
            'scope': 'pairs touching a rotor' if moving_only else 'all solid occurrences',
            'boolean_candidates': len(pairs), 'boolean_completed': completed,
            'boolean_failures': failures, 'intersections': hits,
            'external_count': len(external),
            'supplier_internal_count': len(hits)-len(external),
            'passed_external': not external and not failures and completed == len(pairs),
            'threshold_volume_mm3': EPS_VOLUME,
            'note': 'Broadphase skips <=1e-5 mm bounding-box penetration. Contact is not a volumetric intersection.'}


def motion_scan(d, loaded):
    # All moved and static shapes below come from the actual exported STEP.
    values = list(np.arange(0, d.config['opening_max_deg']+1e-8,
                            d.config['motion_sample_step_deg']))
    if values[-1] < d.config['opening_max_deg']:
        values.append(d.config['opening_max_deg'])
    result = []
    for a in values:
        move = d.hand_world * rotate_about(PIVOT, (0, 0, 1), -a) * d.hand_world.inverse
        pose = [Item(i.key, i.original_path, i.shape, move*i.loc if i.role == 'rotor' else i.loc,
                     i.unit, i.role, i.color) for i in loaded]
        r = scan(pose, moving_only=True, include_internal=False)
        result.append({'opening_deg': float(a), **r})
    return {'angles': result, 'passed': all(r['passed_external'] for r in result),
            'not_verified': ['Clearance between sampled poses except the separate new-mount AABB bound',
                             'Other arm-joint poses', 'Deformation, backlash and real cable motion']}


def bijective_match(a, b, tolerance=EPS_LENGTH):
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape or a.ndim != 2 or len(a) == 0:
        return {'passed': False, 'count_reference': len(a), 'count_candidate': len(b), 'max_error_mm': None}
    distance = np.linalg.norm(a[:, None] - b[None, :], axis=-1)
    ii, jj = linear_sum_assignment(distance)
    err = float(distance[ii, jj].max())
    return {'passed': err <= tolerance, 'count_reference': len(a), 'count_candidate': len(b),
            'max_error_mm': err, 'assignment': jj.tolist()}


def cylinder_axes(shape, direction, radius):
    direction = np.array(direction, float); direction /= np.linalg.norm(direction)
    result = []
    for f in shape.Faces():
        a = BRepAdaptor_Surface(f.wrapped)
        if a.GetType() != GeomAbs_Cylinder or f.wrapped.Orientation() != TopAbs_REVERSED:
            continue
        cyl = a.Cylinder(); ax = cyl.Axis(); vv = ax.Direction(); pp = ax.Location()
        v = np.array([vv.X(), vv.Y(), vv.Z()])
        if abs(np.dot(direction, v)) < 1-1e-8 or abs(cyl.Radius()-radius) > EPS_LENGTH:
            continue
        p = np.array([pp.X(), pp.Y(), pp.Z()])
        p -= direction*np.dot(p, direction)
        if not any(np.linalg.norm(p-old) < EPS_LENGTH for old in result):
            result.append(p)
    return np.array(result)


def empty_cylindrical_path(shape, origin, direction, radius, length):
    probe = cq.Solid.makeCylinder(radius, length, cq.Vector(*origin), cq.Vector(*direction))
    return volume(shape.intersect(probe)) < EPS_VOLUME


def check_interfaces(d, loaded):
    hand = {i.key: i.world.moved(d.hand_world.inverse) for i in loaded}
    static = hand[f'original_{d.static_index:03d}']
    wrist_key = next(i.key for i in loaded if i.original_path.endswith('/XL,XC-330 v1:6/DC15_A01_HORN_DUMMY:1'))
    horn, bridge = hand[wrist_key], hand['wrist_camera_bridge']
    axis = np.array([0., 1., 0.]); expected = MOUNT_POINTS.copy(); expected[:, 1] = 0
    records = {
        'static_four_bores': bijective_match(expected, cylinder_axes(static, axis, 1.15)),
        'bridge_four_bores': bijective_match(expected, cylinder_axes(bridge, axis, 1.15)),
        'wrist_horn_four_small_bores': bijective_match(expected, cylinder_axes(horn, axis, .8))}
    # Probe the measured open portion, not an infinite cylinder through other holes.
    passages = []
    for p in MOUNT_POINTS:
        origin = [p[0], MOUNT_CENTER[1]-3.999, p[2]]
        passages.append(empty_cylindrical_path(bridge, origin, axis, 1.14, 3.998))
    records['bridge_through_paths'] = {'passed': all(passages), 'per_hole': passages}
    # Faces meet at the two separate physical planes; not just coincident axes.
    front = cq.Solid.makeBox(100, .0002, 100, cq.Vector(-50, MOUNT_CENTER[1]-.0001, -30))
    rear = cq.Solid.makeBox(100, .0002, 100, cq.Vector(-50, MOUNT_CENTER[1]-4-.0001, -30))
    front_material = volume(bridge.intersect(front)) / .0001
    rear_material = volume(bridge.intersect(rear)) / .0001
    records['flange_material_at_both_seats'] = {
        'passed': front_material > 100 and rear_material > 100,
        'front_section_approx_mm2': front_material, 'rear_section_approx_mm2': rear_material,
        'plane_separation_mm': 4.0,
        'note': 'Thin-slice material test; not a pressure/contact stress or thread check'}
    r, up, fwd = camera_basis(d.config)
    cam_centres = np.array([camera_point(d.config, u, v) for u in (-14,14) for v in (-14,14)])
    cam_centres -= (cam_centres @ fwd)[:, None]*fwd
    for key in ['uvc28_camera_carrier', 'uvc28_pcb_spacer_4mm', 'ASSUMED_camera_pcb']:
        records[key+'_four_bores'] = bijective_match(cam_centres, cylinder_axes(hand[key], fwd, 1.15))
    mount_centres = np.array([camera_point(d.config, u, -24) for u in (-12,12)])
    mount_centres -= (mount_centres @ fwd)[:, None]*fwd
    for key in ['wrist_camera_bridge', 'uvc28_camera_carrier']:
        records[key+'_m3_pair'] = bijective_match(mount_centres, cylinder_axes(hand[key], fwd, 1.6))
    return {'checks': records, 'passed': all(x['passed'] for x in records.values()),
            'not_verified': ['Horn threads, permissible screw engagement and torque',
                             'As-built camera hole sizes and screw stack', 'Tool access with actual tools']}


def baseline_items(d):
    return [Item(i.key,i.original_path,i.shape,
                 d.baseline.revised_locations[int(i.key.split('_')[1])],i.unit,i.role,i.color)
            for i in d.items if i.key.startswith('original_')]


def preservation(d, loaded, control=None):
    # Measure a NO-OP save/read of the same imported source B-reps. STEP transfer
    # can change trim-curve mass integration on old vendor CAD even with identical
    # vertices/bounds/topology. Compare against that independently serialized
    # control rather than mislabelling this effect as a design change or hiding it.
    if control is None:
        control=reload_items(DEFAULT_OUT/'CAD/reference/mixed_baseline_noop.step',baseline_items(d))
    controls={i.key:i for i in control}
    reloaded = {i.key: i for i in loaded}
    records = []; upstream_error = 0.
    for original in d.baseline.original:
        k = f'original_{original.index:03d}'
        expected = next(i for i in d.items if i.key == k)
        actual = reloaded[k]
        a, b = expected.world, actual.world
        av = np.array([v.toTuple() for v in a.Vertices()])
        bv = np.array([v.toTuple() for v in b.Vertices()])
        vertex_error = max(float(cKDTree(av).query(bv)[0].max()), float(cKDTree(bv).query(av)[0].max())) if len(av) and len(bv) else 0.
        vdelta, adelta = abs(volume(a)-volume(b)), abs(a.Area()-b.Area())
        bbox_error = float(np.max(np.abs(np.array(bounds(a))-np.array(bounds(b)))))
        directly_reused = expected.shape.wrapped.IsSame(d.baseline.revised_shapes[original.index].wrapped)
        if expected.role == 'upstream':
            err = float(np.max(np.abs(matrix(expected.loc)-matrix(d.baseline.revised_locations[original.index]))))
            upstream_error = max(upstream_error, err)
        undo=d.baseline.revised_locations[original.index]*expected.loc.inverse
        unposed=b.moved(undo);ref=controls[k].world
        control_vdelta=abs(volume(unposed)-volume(ref));control_adelta=abs(unposed.Area()-ref.Area())
        raw_relative_volume=vdelta/max(volume(a),1.)
        raw_relative_area=adelta/max(a.Area(),1.)
        control_bbox_error=float(np.max(np.abs(np.array(bounds(unposed))-np.array(bounds(ref)))))
        passed = (directly_reused and vertex_error < 1e-4 and bbox_error < 1e-4 and
                  raw_relative_volume < 1e-4 and raw_relative_area < 1e-4 and
                  control_vdelta < max(.001, volume(ref)*1e-7) and
                  control_adelta < max(.001, ref.Area()*1e-7) and control_bbox_error<1e-4 and
                  len(a.Solids()) == len(b.Solids()) and len(a.Faces()) == len(b.Faces()))
        records.append({'key': k, 'role': expected.role, 'original_path': original.path,
                        'same_source_brep': directly_reused, 'source_and_reloaded_faces': [len(a.Faces()),len(b.Faces())],
                        'source_and_reloaded_solids': [len(a.Solids()),len(b.Solids())],
                        'roundtrip_vertex_hausdorff_mm': vertex_error, 'roundtrip_bbox_error_mm': bbox_error,
                        'roundtrip_volume_delta_mm3': vdelta, 'roundtrip_area_delta_mm2': adelta,
                        'raw_relative_volume_delta':raw_relative_volume, 'raw_relative_area_delta':raw_relative_area,
                        'vs_noop_control_volume_delta_mm3':control_vdelta,
                        'vs_noop_control_area_delta_mm2':control_adelta,
                        'vs_noop_control_bbox_error_mm':control_bbox_error,
                        'passed': passed})
    return {'source_occurrences': len(records), 'upstream_max_transform_error': upstream_error,
            'records': records, 'passed': upstream_error < 1e-10 and all(x['passed'] for x in records),
            'method': 'Direct source B-rep reuse; STEP roundtrip topology/vertices/bbox; raw mass differences recorded and bounded at 0.01%; after undoing the allowed placement, compare tightly with independent no-op STEP serialization control',
            'serialization_control':'CAD/reference/mixed_baseline_noop.step',
            'scope': 'Unchanged imported shape, not a full redesign. Gripper-module placement is the declared exception.'}


def check_parts(out, d):
    results = {}
    for name in d.parts:
        p = out/'CAD/parts'/name
        shape = cq.importers.importStep(str(p.with_suffix('.step'))).val()
        mesh = trimesh.load_mesh(str(p.with_suffix('.stl')), process=True)
        bbox = bounds(shape)
        mesh_bbox_err = float(np.max(np.abs(mesh.bounds.ravel()-bbox)))
        relative_volume = abs(mesh.volume-volume(shape))/volume(shape)
        r = {'valid_brep': bool(shape.isValid()), 'solids':len(shape.Solids()), 'bounds_mm': bbox,
             'volume_mm3':volume(shape), 'stl_watertight':bool(mesh.is_watertight),
             'stl_winding_consistent':bool(mesh.is_winding_consistent), 'stl_positive_volume':bool(mesh.volume>0),
             'stl_brep_bbox_max_error_mm':mesh_bbox_err, 'stl_brep_relative_volume_error':float(relative_volume),
             'stl_triangles':len(mesh.faces)}
        r['passed'] = (r['valid_brep'] and r['solids']==1 and r['stl_watertight'] and r['stl_winding_consistent']
                       and r['stl_positive_volume'] and mesh_bbox_err<.1 and relative_volume<.01)
        results[name] = r
    return {'parts':results, 'total_solid_volume_cm3':sum(r['volume_mm3'] for r in results.values())/1000,
            'passed':all(x['passed'] for x in results.values()),
            'note':'STL/B-rep integrity is not print/process/strength/fit approval. No slicer or G-code is included.'}


def continuous_mount_bound(d, loaded):
    hand = {i.key:i.world.moved(d.hand_world.inverse) for i in loaded}
    bb = np.array(bounds(hand[f'original_{d.moving_index:03d}']))
    # For 0 <= theta <= 50 deg, y'=py -(x-px)sin(theta)+(y-py)cos(theta).
    # Since sin/cos >=0, the entire moving B-rep is bounded using xmax and ymin.
    a, b = bb[3]-PIVOT[0], PIVOT[1]-bb[1]
    critical = math.degrees(math.atan2(a,b))
    theta = min(max(critical,0),d.config['opening_max_deg'])
    min_y = PIVOT[1] - a*math.sin(math.radians(theta)) - b*math.cos(math.radians(theta))
    zmax = bb[5]
    cutter = cq.Solid.makeBox(1000,1000,zmax+500,cq.Vector(-500,-500,-500))
    records = {}
    for key in list(d.parts)+list(d.proxies):
        low = hand[key].intersect(cutter)
        if low.Solids() and volume(low)>EPS_VOLUME:
            ymax = bounds(low)[4]
            gap = min_y-ymax
            records[key] = {'low_zone_max_y_mm':ymax, 'separation_lower_bound_mm':gap, 'passed':gap>0}
        else:
            records[key] = {'above_jaw_z_envelope':True, 'vertical_gap_mm':bounds(hand[key])[2]-zmax,
                            'passed':bounds(hand[key])[2]>=zmax-1e-5}
    return {'jaw_y_sweep_lower_bound_mm':min_y, 'jaw_z_upper_bound_mm':zmax,
            'critical_opening_deg':theta, 'new_parts':records,
            'passed':all(r['passed'] for r in records.values()),
            'scope':'Conservative continuous AABB separation of the rotating jaw from NEW mount and assumed camera only, for 0..50 deg; no whole-arm claim.'}


def fabrication_gate(geometric_pass, evidence_files=()):
    # Explicitly fail closed: no validated engineering signoff is implemented.
    # Neither setting config booleans nor passing any paths bypasses this gate.
    return {'accepted_for_fabrication':False, 'geometry_passed':bool(geometric_pass),
            'blockers':['Actual camera and lens are not identified/measured',
                        'Wrist fastener length, threads, engagement and assembly access not physically verified',
                        'Printed strength, stiffness, payload and fatigue not verified',
                        'Actual USB wiring and full arm-joint swept motion not verified',
                        'Physical fitting and calibrated image test not performed'],
            'evidence_policy':'A separate reviewed engineering revision is required; flags and file existence cannot grant acceptance.'}
