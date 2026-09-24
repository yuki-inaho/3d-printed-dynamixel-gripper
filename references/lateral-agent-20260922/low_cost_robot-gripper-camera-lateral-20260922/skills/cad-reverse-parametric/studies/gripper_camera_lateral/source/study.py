#!/usr/bin/env python3
"""Build/re-import/review the source-preserving lateral-camera prototype.

From the repository root:
  python skills/cad-reverse-parametric/studies/gripper_camera_lateral/source/study.py build
  ... study.py validate
  ... study.py print-package   # ALWAYS blocked until a separately reviewed revision
"""
from __future__ import annotations
import argparse
import json
import platform
import sys
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from design import (build, load_config, DEFAULT_OUT, STUDY, REPO, TOOLKIT, Item,
                    assembly, hand_items, bounds, sha256, camera_basis,
                    camera_optical_center, verify_sources)
from review import (matrix, reload_items, scan, motion_scan, check_interfaces,
                    preservation, check_parts, continuous_mount_bound, fabrication_gate, baseline_items)
from vision import check_vision, render_camera
from render_cad import render


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    def convert(value):
        if isinstance(value, np.generic):return value.item()
        if isinstance(value, np.ndarray):return value.tolist()
        raise TypeError(f'Unsupported JSON value: {type(value).__name__}')
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False, default=convert)+'\n')


def export(d, out):
    (out/'CAD/parts').mkdir(parents=True, exist_ok=True)
    for name, shape in d.parts.items():
        path = out/'CAD/parts'/name
        cq.exporters.export(shape, str(path.with_suffix('.step')))
        cq.exporters.export(shape, str(path.with_suffix('.stl')), tolerance=.02, angularTolerance=.08)
    for a in (0,d.config['opening_max_deg']):
        tag = f'{a:g}deg'
        assembly(d.at_opening(a), 'lateral_camera_'+tag).save(str(out/f'CAD/full_arm_{tag}.step'))
        assembly(hand_items(d,a), 'hand_camera_'+tag).save(str(out/f'CAD/hand_{tag}.step'))
    (out/'CAD/reference').mkdir(exist_ok=True)
    assembly(baseline_items(d),'mixed_baseline_noop').save(str(out/'CAD/reference/mixed_baseline_noop.step'))
    write_json(out/'configuration.json', d.config)
    # Right/down/forward optical convention: suitable for camera extrinsic data,
    # NOT a ready-to-install robot calibration or an automatic homing command.
    r, up, f = camera_basis(d.config)
    Hopt = np.eye(4); Hopt[:3,:3] = np.column_stack([r,-up,f]); Hopt[:3,3] = camera_optical_center(d.config)
    write_json(out/'kinematics.json', {
        'length_unit':'mm','optical_frame':'x right, y down, z forward',
        'H_to_world':matrix(d.hand_world).tolist(), 'optical_to_H':Hopt.tolist(),
        'optical_to_world':(matrix(d.hand_world)@Hopt).tolist(),
        'module_change_world':matrix(d.hand_world*d.static_source_location.inverse).tolist(),
        'clocking_deg':90,'axial_added_tool_length_mm':4,
        'calibrated':False,
        'warning':'Reference CAD pose only. Update/recalibrate TCP, camera extrinsics and controller limits before use; firmware and URDF are untouched.'})
    source_files = {str(p.relative_to(REPO)):sha256(p) for p in (REPO/'hardware/follower/step').glob('*.step')}
    write_json(out/'source_manifest.json', {
        'revision':d.config['revision'],'source_hashes':source_files,
        'baseline_required_hashes':verify_sources(REPO/'hardware/follower/step'),
        'code_hashes':{str(p.relative_to(REPO)):sha256(p) for p in sorted((STUDY/'source').glob('*.py'))},
        'config_sha256':sha256(STUDY/'design.json'),
        'environment':{'python':platform.python_version(),'cadquery':cq.__version__,
                       'trimesh':trimesh.__version__,'numpy':np.__version__,
                       'locked_uv_sync':'Not executed successfully: Python 3.12.12 download failed (network DNS unavailable). Existing lockfile unchanged.'},
        'occurrences':[{'key':i.key,'source_path':i.original_path,'role':i.role,'physical_unit':i.unit,
                        'world_transform':matrix(i.loc).tolist(),'solids':len(i.shape.Solids())} for i in d.items],
        'cad_status':'PROTOTYPE / NOT ACCEPTED FOR FABRICATION'})


def verify_export_binding(out):
    expected = json.loads((out/'source_manifest.json').read_text())
    for p, digest in expected['code_hashes'].items():
        if sha256(REPO/p) != digest:
            raise ValueError('Study code changed since export; rebuild: '+p)
    for p, digest in expected['source_hashes'].items():
        if sha256(REPO/p) != digest:
            raise ValueError('Protected input changed since export: '+p)
    if json.loads((out/'configuration.json').read_text()) != load_config():
        raise ValueError('Configuration changed since export; rebuild the prototype')
    # Binary artifacts are bound after export, before validation.
    for p, digest in json.loads((out/'cad_hashes.json').read_text()).items():
        if sha256(out/p) != digest:
            raise ValueError('CAD artifact changed since export: '+p)


def validate(d, out):
    verify_export_binding(out)
    print('Re-importing exported assemblies', flush=True)
    closed = reload_items(out/'CAD/full_arm_0deg.step', d.at_opening(0))
    opened = reload_items(out/f"CAD/full_arm_{d.config['opening_max_deg']:g}deg.step", d.at_opening(d.config['opening_max_deg']))
    control=reload_items(out/'CAD/reference/mixed_baseline_noop.step',baseline_items(d))
    report = {'status':'GEOMETRY_REVIEW_PROTOTYPE_NOT_FABRICATION_APPROVED',
              'parts':check_parts(out,d), 'preservation':preservation(d,closed,control),
              'interfaces':check_interfaces(d,closed),
              'continuous_new_mount_separation':continuous_mount_bound(d,closed)}
    print('Exact all-pair closed-pose collision scan', flush=True)
    report['closed_pose_collisions'] = scan(closed)
    print('Exact all-pair open-pose collision scan', flush=True)
    report['open_pose_collisions'] = scan(opened)
    print('Jaw-motion collision samples', flush=True)
    report['jaw_motion'] = motion_scan(d,closed)
    print('Camera visibility samples, using re-imported full-arm scene', flush=True)
    report['vision'] = check_vision(d,items_override=d.in_hand(closed))
    report['geometry_passed'] = all([
        report['parts']['passed'],report['preservation']['passed'],report['interfaces']['passed'],
        report['continuous_new_mount_separation']['passed'],
        report['closed_pose_collisions']['passed_external'],report['open_pose_collisions']['passed_external'],
        report['jaw_motion']['passed'],report['vision']['passed']])
    report['fabrication_gate'] = fabrication_gate(report['geometry_passed'])
    write_json(out/'reports/validation.json',report)
    print('geometry_passed =',report['geometry_passed'],flush=True)
    return report


def make_previews(d, out):
    folder=out/'preview';folder.mkdir(exist_ok=True)
    for angle in (0,25,d.config['opening_max_deg']):
        if angle>d.config['opening_max_deg']:continue
        items=hand_items(d,angle)
        render([(i.world,i.color) for i in items if i.shape.Solids()], folder/f'hand_{angle:g}deg.png',direction=(1,-1,1),size=(1400,1100))
        render_camera(items,d.config,folder/f'camera_{angle:g}deg.png')
    # Full arm in the revised reference pose.
    render([(i.world,i.color) for i in d.at_opening(25) if i.shape.Solids()],folder/'full_arm.png',direction=(1,-1,1),size=(1300,1400))
    # Same world viewpoint and frame for the mechanically clocked before/after.
    # Render the wrist neighborhood in the original static-jaw frame S.
    after=[Item(i.key,i.original_path,i.shape,d.static_source_location.inverse*i.loc,i.unit,i.role,i.color)
           for i in d.items if i.role!='upstream' or any(x in i.original_path for x in (
               '/XL,XC-330 v1:6/','/servo connector angle v4:1/','/XL,XC-330 v1:8/'))]
    original={r.index:r for r in d.baseline.original}
    before=[]
    for i in after:
        if not i.key.startswith('original_'):continue
        idx=int(i.key.split('_')[1]);rr=original[idx]
        before.append((d.baseline.revised_shapes[idx].moved(d.static_source_location.inverse*d.baseline.revised_locations[idx]),i.color))
    ash=[(i.world,i.color) for i in after if i.shape.Solids()]
    for label,direction in [('X',(1,0,0)),('Y',(0,1,0)),('Z',(0,0,1))]:
        render(before,folder/f'before_{label}.png',direction=direction,size=(1100,1000),focus=(0,0,15),scale=100)
        render(ash,folder/f'after_{label}.png',direction=direction,size=(1100,1000),focus=(0,0,15),scale=100)
    for name,shape in d.parts.items():
        render([(shape,(.90,.54,.16) if 'bridge' in name else (.72,.77,.82))],folder/f'{name}.png',direction=(1,-1,1),size=(900,800))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['build','validate','print-package'])
    parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    parser.add_argument('--skip-previews',action='store_true')
    args=parser.parse_args();d=build();out=args.out.resolve()
    if args.command=='build':
        export(d,out)
        write_json(out/'cad_hashes.json',{str(p.relative_to(out)):sha256(p) for p in sorted((out/'CAD').rglob('*')) if p.is_file()})
    result=validate(d,out)
    if args.command=='print-package':
        print(json.dumps(result['fabrication_gate'],ensure_ascii=False,indent=2))
        return 2
    if args.command=='build' and not args.skip_previews:
        make_previews(d,out)
    return 0 if result['geometry_passed'] else 1

if __name__=='__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        raise
