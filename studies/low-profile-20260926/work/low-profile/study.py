"""Explicit low-profile search on locally extended source gripper CAD."""
import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

from design import extended_arm, load_source

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'work/optimization'))
from optimize import pose, view_metrics
from mechanics import project_points
from gripper_design.camera_overhead_r4 import box, retained_at
from scripts.camera_view_d405_r5 import cases
from scripts.camera_view_r4 import View

OUT = ROOT / 'outputs/low-profile-250g'
SIZE = (848, 480)
CENTER = np.array([-.2, 214.6, 164.6])


def save(name, data):
    (OUT / 'reports').mkdir(parents=True, exist_ok=True)
    (OUT / 'reports' / name).write_text(json.dumps(data, indent=2))


def target_center(delta):
    return CENTER + [0, delta, 0]


def cube(edge, delta):
    c = target_center(delta)
    h = edge / 2
    return box(*(x for pair in zip(c-h, c+h) for x in pair))


def screen(p, delta):
    result = []
    for edge, side in itertools.product([10, 20, 30], ['left', 'right']):
        pts = np.array(list(itertools.product([-edge/2, edge/2], repeat=3))) + target_center(delta)
        inside, depth = project_points(pts, p['eyes'][side], p['direction'], p['up'])
        result.append({'edge': edge, 'side': side, 'inside': bool(inside.all()), 'min_depth_mm': float(depth.min())})
    return result


def search():
    source = load_source()
    all_rows = []
    for extension in range(0, 31, 5):
        rows = []
        for pitch, y, z in itertools.product(range(30, 51, 5), range(120, 196, 5), range(205, 246, 5)):
            p = pose([-.2, y, z], pitch)
            checks = screen(p, extension)
            row = {'id': f'E{extension}_P{pitch}_Y{y}_Z{z}', 'extension_mm': extension, 'pitch': pitch,
                   'pose': p, 'screen': checks, 'screen_pass': all(v['inside'] and v['min_depth_mm'] >= 75 for v in checks),
                   'bare_optics': [], 'bare_optics_pass': False}
            rows.append(row)
        arm = extended_arm(source, extension)
        active = [r for r in rows if r['screen_pass']]
        print('extension', extension, 'grid', len(rows), 'projection_pass', len(active), flush=True)
        # Rejection at any target size is decisive. Other sizes are explicitly not evaluated for rejected rows.
        for label, angle, edge in reversed(cases()):
            if not edge or not active:
                continue
            scene = retained_at(arm, angle) | {'DIAGNOSTIC_CUBE': cube(edge, extension)}
            view = View(scene, (0,0,0), (0,1,0), (0,0,1), 84, SIZE)
            surviving = []
            for idx, r in enumerate(active):
                minimum = 1.0
                for side in ['left', 'right']:
                    metric = view_metrics(view, r['pose'], side, cube_only=True)['cube']
                    r['bare_optics'].append({'edge': edge, 'side': side, **metric})
                    minimum = min(minimum, metric['visible_fraction'])
                if minimum >= .9:
                    surviving.append(r)
                if idx % 100 == 0:
                    print('render', extension, edge, idx, '/', len(active), 'surviving', len(surviving), flush=True)
            view.close()
            active = surviving
            print('case done', extension, edge, 'surviving', len(active), flush=True)
        for r in active:
            r['bare_optics_pass'] = len(r['bare_optics']) == 6
            r['minimum_cube_visible'] = min(v['visible_fraction'] for v in r['bare_optics'])
        all_rows += rows
        save('search.json', {'grid': all_rows, 'mount_in_scene': False, 'resolution': SIZE,
                             'rejection_short_circuit': True, 'finished_extension_mm': extension})
        print('EXTENSION COMPLETE', extension, 'passing', [r['id'] for r in active], flush=True)
    passed = [r for r in all_rows if r['bare_optics_pass']]
    save('optical-shortlist.json', sorted(passed, key=lambda r: (r['pitch'], r['extension_mm'], r['pose']['glass'][2], r['pose']['glass'][1])))
    print('SEARCH COMPLETE', len(all_rows), 'passing', len(passed), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['search'])
    args = parser.parse_args()
    if args.action == 'search':
        search()
