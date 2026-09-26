"""Read-only source intake and face inventory for local finger extension."""
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path('/home/inaho-omen/Project/3d-printed-dynamixel-gripper')
sys.path.insert(0, str(REPO))
from scripts.assembly_io import bounds, read_step

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/low-profile-250g'
SOURCE = REPO / 'outputs/camera-mount-id5-overhead-d405-r5/CAD/ID5_D405_mid_ASSEMBLY.step'
COMPACT = ROOT / 'outputs/optimization-250g/CAD/Robot_250g_compact_D405.step'
REF = Path(__file__).parent / 'cache'
COMMIT = '305ad0f6e8f19e4e739616160cbdc7cae1ab153f'


def main():
    (OUT / 'reports').mkdir(parents=True, exist_ok=True)
    REF.mkdir(exist_ok=True)
    refname = 'RB9.01.060.110 D405 holder.STL'
    url = f'https://raw.githubusercontent.com/roboninecom/SO-ARM100-101-Parallel-Gripper/{COMMIT}/models/parts/' + urllib.parse.quote(refname)
    target = REF / refname
    if not target.exists():
        target.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    rows = read_step(SOURCE)[2]
    report = {'inputs': [dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size) for p in (SOURCE, COMPACT, target)], 'reference_url': url, 'parts': {}}
    for row in rows:
        if not any(k in row.name for k in ('finger_', 'pad_', 'carriage_')):
            continue
        s = row.world
        report['parts'][row.name] = {'bounds': bounds(s), 'volume': s.Volume(), 'solids': len(s.Solids()), 'faces': []}
        for face in s.Faces():
            if face.geomType() != 'PLANE':
                continue
            report['parts'][row.name]['faces'].append({'area': face.Area(), 'center': face.Center().toTuple(), 'normal': face.normalAt().toTuple(), 'bounds': bounds(face)})
    import trimesh
    mesh = trimesh.load(target)
    report['reference_mesh'] = {'bounds': mesh.bounds.tolist(), 'watertight': bool(mesh.is_watertight), 'principal_planar_normals': []}
    normals = {}
    for norm, area in zip(mesh.face_normals, mesh.area_faces):
        key = tuple(round(float(x), 4) for x in norm)
        normals[key] = normals.get(key, 0) + float(area)
    report['reference_mesh']['principal_planar_normals'] = sorted([{'normal': k, 'area': a} for k, a in normals.items()], key=lambda x: -x['area'])[:12]
    (OUT / 'reports/input-intake.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: {j: x for j, x in v.items() if j != 'faces'} for k, v in report['parts'].items()}, indent=2))
    print(json.dumps(report['reference_mesh'], indent=2))


if __name__ == '__main__':
    main()
