"""Release gate for the frozen PG2 R5 digital prototype.

This aggregates actual reports, rejects stale evidence, and writes a traceability record.
It does not replace geometric tests and cannot approve physical hardware.
Run from any directory; paths are resolved relative to this source tree.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'R5'
CAMERA_REVISION = 'C3'


def load(name: str) -> Any:
    path = ROOT / 'reports' / name
    if not path.is_file():
        raise RuntimeError(f'Missing evidence: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def fresh(result: str, dependencies: list[str]) -> None:
    """The issued report must be newer than each of its source dependencies."""
    stamp = (ROOT / result).stat().st_mtime
    for rel in dependencies:
        require(stamp >= (ROOT / rel).stat().st_mtime, f'Stale evidence: {result} predates {rel}')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate() -> dict[str, Any]:
    shape_sources = ['source/design.py', 'source/camera.py', 'source/assembly_reader.py']
    export = load('export_audit.json')
    require(export['revision'] == REVISION and export['pass'], 'Export audit failed or wrong revision')
    require(export['guardrails']['positive'], 'Positive architecture guard failed')
    negative = export['guardrails']['negative_tests']
    require(len(negative) == 12 and all(t['rejected'] for t in negative), 'Negative tests not all rejected')
    require(len(export['stl']) == 12 and all(t['pass'] for t in export['stl'].values()), 'STL audit incomplete')
    require(len(export['step']) == 16 and all(t['pass'] for t in export['step'].values()), 'STEP audit incomplete')
    fresh('reports/export_audit.json', shape_sources + ['source/guardrails.py', 'source/calibration.py', 'source/build_release.py'])
    for name in export['stl']:
        require((ROOT / 'STL' / name).is_file(), f'Missing issued mesh: {name}')
        require((ROOT / 'STL' / name).stat().st_mtime <= (ROOT / 'reports/export_audit.json').stat().st_mtime, 'Mesh changed after audit')
    for name in export['step']:
        require((ROOT / name).is_file(), f'Missing issued STEP: {name}')
        require((ROOT / name).stat().st_mtime <= (ROOT / 'reports/export_audit.json').stat().st_mtime, 'STEP changed after audit')
    # No missing or duplicated angular samples may be hidden by a Boolean overall flag.
    all_angles: list[int] = []
    min_clearances = {'frame': float('inf'), 'retainer_top': float('inf'), 'retainer_bottom': float('inf')}
    boolean_count = 0
    for i in range(4):
        name = f'sweep_{i}.json'
        sweep = load(name)
        require(sweep['revision'] == REVISION and sweep['all_parts_including_camera'], 'Sweep uses wrong model')
        require(not sweep['collisions'] and sweep['clearance_pass'], f'Sweep {i} failed')
        require(len(sweep['guide_clearances']) == len(sweep['angles']), 'Guide distance samples missing')
        fresh('reports/' + name, shape_sources + ['source/guardrails.py', 'source/review_iteration.py', 'source/validate_worker.py'])
        all_angles.extend(sweep['angles'])
        boolean_count += sweep['boolean_tests']
        for row in sweep['guide_clearances']:
            require(row['pass'] and min(row['minimums_mm'].values()) > .1499, 'Guide gap is insufficient')
            for k, value in row['minimums_mm'].items():
                min_clearances[k] = min(min_clearances[k], value)
    require(sorted(all_angles) == list(range(30, 141)), '111-pose angular coverage is not exact')
    saved = load('saved_step_collisions.json')
    require(saved['pass'] and len(saved['checks']) == 4, 'Saved assembly check incomplete')
    for row in saved['checks']:
        require(row['revision'] == REVISION and row['pass_'] and not row['collisions'] and row['clearance_pass'], 'Saved STEP failed')
    fresh('reports/saved_step_collisions.json', shape_sources + ['source/check_saved.py', 'source/guardrails.py', 'source/review_iteration.py'])
    regression = load('frame_roundtrip_regression.json')
    require(regression['revision'] == REVISION and regression['pass'], 'Serialized frame/nut regression failed')
    fresh('reports/frame_roundtrip_regression.json', shape_sources + ['source/check_frame_roundtrip.py'])
    engineering = load('engineering_checks.json')
    require(engineering['revision'] == REVISION and engineering['pass'], 'Engineering checks failed')
    require(engineering['kinematics']['samples'] == 1101, 'Kinematic coverage incomplete')
    require(engineering['tool_access']['count'] == 32 and all(t['pass'] for t in engineering['tool_access']['tests']), 'Tool access failed')
    require(len(engineering['actual_jaw_symmetry']['tests']) == 3, 'BRep symmetry check missing')
    board_tools = [t for t in engineering['tool_access']['tests'] if t['name'].startswith('camera_M2_')]
    require(len(board_tools) == 4 and all(t.get('assembly_stage', '').startswith('C1:') for t in board_tools), 'Camera board assembly sequence not encoded')
    fresh('reports/engineering_checks.json', shape_sources + ['source/engineering_checks.py'])
    camera = load('camera_C3_delta.json')
    require(camera['core_revision'] == REVISION and camera['camera_revision'] == CAMERA_REVISION and camera['pass'], 'Camera evidence stale or failed')
    require(camera['angles'] == list(range(30, 141)), 'Camera delta coverage incomplete')
    require(len(camera['optical_model']['rays']) == 54 and all(t['pass'] for t in camera['optical_model']['rays']), 'Optical ray check incomplete')
    fresh('reports/camera_C3_delta.json', shape_sources + ['source/check_camera_delta.py'])
    inventory = load('print_inventory.json')
    core = [t for t in inventory if t['category'] == 'core']
    require(len(core) == 6 and sum(t['quantity'] for t in core) == 9, 'Core print quantities changed')
    images = ['overview.png', 'open_iso.png', 'open_front.png', 'closed_front.png', 'side.png', 'rear.png', 'exploded.png', 'print_layout.png', 'camera_optional.png', 'motion.gif']
    for name in images:
        path = ROOT / 'images' / name
        require(path.is_file(), f'Missing final view: {name}')
        with Image.open(path) as im:
            im.verify()
        fresh('images/' + name, shape_sources)
    visual = load('visual_review.json')
    require(visual['revision'] == REVISION and visual['pass'], 'Visual review incomplete')
    for name, digest in visual['reviewed_image_sha256'].items():
        require(sha256(ROOT / 'images' / name) == digest, f'Image changed after visual review: {name}')
    for name in ['START_HERE_ja.md', 'docs/WORK_ORDER_ja.md', 'docs/ASSEMBLY_AND_PRINT_ja.md', 'docs/PHYSICAL_ACCEPTANCE_ja.md', 'source/README_ja.md']:
        require((ROOT / name).is_file(), f'Missing work document: {name}')
    status = [
        ('D01', '要求追跡・禁止例', '12種類の意図的違反をすべて拒否', ['export_audit.json']),
        ('D02', 'XL430取付基準', '添付CADとメーカー仕様・取付図を照合。側面ねじ侵入2.75 mm', ['engineering_checks.json', 'export_audit.json']),
        ('D03', '左右対称の運動', '1101点の機構計算、3姿勢の実形状対称性、端点余裕', ['engineering_checks.json']),
        ('D04', '締結込み干渉', '本体R5＋カメラC3の111姿勢。保存後4組立STEPも再検査', [f'sweep_{i}.json' for i in range(4)] + ['saved_step_collisions.json']),
        ('D05', '案内・抜け止め・工具', '正の案内距離、最小かかり2.4 mm、工程別工具軸32件', ['engineering_checks.json'] + [f'sweep_{i}.json' for i in range(4)]),
        ('D06', '出力健全性', 'STL12点・STEP16点。ナット座の保存再読込回帰検査', ['export_audit.json', 'frame_roundtrip_regression.json']),
        ('D07', '製作作業書', '数量・ねじ長・隙間・印刷支え・組立順・現物未完項目を記載', ['../docs/ASSEMBLY_AND_PRINT_ja.md', '../docs/WORK_ORDER_ja.md']),
        ('D08', '実CAD表示と再生成', '斜視・正面・側面・分解・印刷姿勢・開閉の画像を目視確認', ['visual_review.json', '../source/README_ja.md'])]
    trace = [
        {'requirement':'R01', 'implementation':'XL430-W250 1台、専用側面タップねじ、既製出力部', 'evidence':['D01','D02']},
        {'requirement':'R02', 'implementation':'長辺Y、出力+Z、爪突出+Zを実形状で検査', 'evidence':['D01','D02','D08']},
        {'requirement':'R03', 'implementation':'前面クランク・2リンク、短い窓付き直動爪', 'evidence':['D03','D04','D08']},
        {'requirement':'R04', 'implementation':'印刷角形ガイドと印刷関節肩、金属棒・軸受・カラーなし', 'evidence':['D01','D05','D07']},
        {'requirement':'R05', 'implementation':'本体6種9個を別体印刷、圧入・印刷スプラインなし', 'evidence':['D01','D06','D07']},
        {'requirement':'R06', 'implementation':'総隙間0.5/0.7/0.9選択、試験片、実形状の正の隙間', 'evidence':['D01','D05','D06','D07']},
        {'requirement':'R07', 'implementation':'正面・側面・斜視を参照と比較。投影の回転だけで済ませない', 'evidence':['D01','D08']},
        {'requirement':'R08', 'implementation':'任意のC3カメラ台2部品。実カメラは未確定', 'evidence':['D04','D05','D07','D08']}]
    result = {
        'revision': REVISION, 'camera_revision': CAMERA_REVISION,
        'issued_at_utc': datetime.now(timezone.utc).isoformat(),
        'digital_prototype_DoD_pass': True, 'physical_acceptance_pass': False,
        'physical_acceptance_status':'NOT PERFORMED — print, assembly, friction, strength, grip, electrical commissioning and actual camera are untested',
        'whole_robot_compatibility':'NOT APPROVED',
        'DoD':[{'id':i,'item':item,'result':res,'pass':True,'evidence':ev} for i,item,res,ev in status],
        'metrics':{'motion_poses':len(all_angles),'boolean_common_tests':boolean_count,'guide_minimum_distances_mm':min_clearances,'step_files':len(export['step']),'stl_files':len(export['stl']),'negative_tests':len(negative),'kinematic_samples':engineering['kinematics']['samples'],'tool_shaft_checks':32,'optical_rays':54,'core_print_types':6,'core_print_quantity':9},
        'scope_limits':['nominal 0.7 mm guide variant for motion sweep','discrete poses, not a continuous swept-volume proof','only 4 named servo side tap/pilot engagements are excluded from overlap test','supplier internals are one reference unit','tool shaft envelopes at the documented assembly stage, not human hand clearance','ideal camera rays at 3 poses, not measured full-finger visibility'],
        'requirements': trace}
    (ROOT / 'reports/RELEASE_DOD.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'reports/requirements_traceability.json').write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def write_manifest() -> None:
    """Seal files after generating the human report; archives preserve these exact bytes."""
    ignored = {'MANIFEST.sha256'}
    paths = [p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ignored]
    rows = [f'{sha256(p)}  {p.relative_to(ROOT).as_posix()}' for p in sorted(paths)]
    (ROOT / 'MANIFEST.sha256').write_text('\n'.join(rows)+'\n', encoding='utf-8')


def verify_manifest() -> None:
    for line in (ROOT / 'MANIFEST.sha256').read_text(encoding='utf-8').splitlines():
        expected, relative = line.split('  ', 1)
        require(sha256(ROOT / relative) == expected, f'Hash mismatch: {relative}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal', action='store_true', help='After report generation, hash all release files')
    parser.add_argument('--verify-manifest', action='store_true')
    args = parser.parse_args()
    if args.verify_manifest:
        verify_manifest(); print('MANIFEST VERIFIED')
    elif args.seal:
        write_manifest(); print('MANIFEST WRITTEN')
    else:
        r = evaluate(); print(json.dumps({'digital_prototype_DoD_pass':r['digital_prototype_DoD_pass'],'physical_acceptance_status':r['physical_acceptance_status'],'metrics':r['metrics']}, ensure_ascii=False, indent=2))
