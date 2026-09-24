"""C92-J28: retain compact C7 drive; enlarge contact jaws and inboard shoes.
All dimensions in mm. Construction X opens, Y is up, Z is forward.
Exports apply the original C7 world transform: X opens, Z up, -Y forward.
This is CAD prototype geometry, not a load-qualified gripper.
"""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE_SOURCE = ROOT / 'reference' / 'C7' / 'source'
if str(BASE_SOURCE) not in sys.path:
    sys.path.insert(0, str(BASE_SOURCE))
import design as base

REVISION = 'PG3-C92-XL430-J28-C9'
P = replace(base.P, finger_end=60.7, revision=REVISION)
PAD_DEPTH = 20.0
PAD_HEIGHT = 28.0
PAD_FRONT_MARGIN = 1.0
SHOE_INNER_X = -11.0
CHANGED_PARTS = ('03_carriage_R', '04_carriage_L', '05_finger_R', '06_finger_L')


def finger(p=P):
    """Continuous gripping plate, original two-bolt interface, two outer ribs."""
    cq = base.cq
    plane = cq.Plane(origin=(-p.jaw_inner, 0, 0), xDir=(0, 1, 0), normal=(1, 0, 0))
    plate = (cq.Workplane(plane)
             .center(0, (p.finger_start + p.finger_end)/2)
             .rect(36, p.finger_end - p.finger_start).extrude(5).val())
    plate = cq.Workplane(obj=plate).edges('|X').fillet(1.5).val()
    for y in (-14.0, 14.0):
        lug = base.box(-p.jaw_inner, 9.6, y-3.3, y+3.3,
                       p.finger_mount_z, p.finger_mount_z+3)
        # XZ polygon. Extrusion -Y: plate and lug have a positive 0.2 mm overlap.
        rib_plane = cq.Plane(origin=(0, y+3.3, 0), xDir=(1, 0, 0), normal=(0, -1, 0))
        rib = (cq.Workplane(rib_plane).polyline([
            (-5.7, 35.8), (3.8, 35.8), (-5.7, 46.7)
        ]).close().extrude(6.6).val())
        plate = base.fuse(plate, lug, rib)
        plate = base.cut(plate, base.cyl(1.15, 3.5, (6.3, y, p.finger_mount_z-.2)))
    return plate


def carriage(p=P):
    """Add 4 mm inward support length without moving outer stops or pivot axes."""
    original = base.carriage(p)
    return base.fuse(original,
                     base.box(SHOE_INNER_X, -6.8, 18.5, 21.7, 19.8, 23.8),
                     base.box(SHOE_INNER_X, -6.8, -21.7, -18.5, 19.8, 23.8))


def pad(p=P):
    front = p.finger_end - PAD_FRONT_MARGIN
    return base.box(-p.jaw_inner-p.pad, -p.jaw_inner,
                    -PAD_HEIGHT/2, PAD_HEIGHT/2, front-PAD_DEPTH, front)


def parts(p=P):
    p.validate()
    result = base.parts(p)
    c, f = carriage(p), finger(p)
    result.update({'03_carriage_R': c, '04_carriage_L': base.mirror(c),
                   '05_finger_R': f, '06_finger_L': base.mirror(f)})
    for name, shape in result.items():
        if not shape.isValid() or len(shape.Solids()) != 1 or shape.Volume() <= 0:
            raise ValueError(f'Invalid printable solid: {name}')
    return result


def assembled(a, p=P, d=None, hardware=True, motor=True, world_coords=False):
    result = base.assembled(a, p=p, d=parts(p) if d is None else d,
                            hardware=hardware, motor=motor, world_coords=False)
    by_name = {i.name: i for i in result}
    x = base.pos(a, p)
    right_pad = pad(p)
    for sign, lr in ((1, 'R'), (-1, 'L')):
        shape = right_pad if sign > 0 else base.mirror(right_pad)
        by_name['pad_'+lr].shape = shape.translate((sign*x, 0, 0))
    if world_coords:
        for item in result:
            item.shape = base.world(item.shape)
    return result


def envelope(items):
    import numpy as np
    boxes = np.array([base.bounds(i.shape) for i in items])
    low, high = boxes[:, :3].min(axis=0), boxes[:, 3:].max(axis=0)
    return (high-low).tolist(), [*low.tolist(), *high.tolist()]


def independent_jaw_requirements(d):
    """Shape-based checks; deliberately independent of a parameter-only claim."""
    from check_geometry import common
    right = d['05_finger_R']
    back = base.box(-P.jaw_inner, -P.jaw_inner+5, -14, 14, 39.7, 59.7)
    _, backed_volume = common(right, back)
    dim, _ = envelope(assembled(25, d=d))
    # Probe only the full-length load-bearing land beneath the cap, Y >= 19.
    shoe_probe = base.box(-11, 7, 19, 21.7, 19.8, 23.8)
    _, shoe_volume = common(d['03_carriage_R'], shoe_probe)
    closed = {i.name:i for i in assembled(135, d=d)}
    shoe_clearance = closed['carriage_R'].shape.distance(closed['carriage_L'].shape)
    probe_items = {i.name:i for i in assembled(107.5, d=d)}
    crank_gap = probe_items['carriage_R'].shape.distance(probe_items['crank'].shape)
    b = base.bounds(right)
    results = {
        'width_le_92': dim[0] <= 92.00001,
        'height_le_64': dim[1] <= 64.00001,
        'depth_le_78': dim[2] <= 78.00001,
        'finger_length_ge_28': b[5]-b[2] >= 27.99999,
        'pad_20x28_backed_by_full_5mm': abs(backed_volume-back.Volume()) < .0001,
        'crank_clearance_at_close_approach_ge_0point3': crank_gap >= .29999,
        'inboard_shoe_length_18': abs(shoe_volume-shoe_probe.Volume()) < .0001,
        'opposing_shoes_clearance_ge_1': shoe_clearance >= .99999,
        'opening_48_or_more': base.opening(25, P) >= 48,
        'closing_gap_point3_to_1point5': .3 <= base.opening(135, P) <= 1.5,
    }
    return {'checks':results, 'pass':all(results.values()),
            'dimensions_WHD_mm':dim, 'opposing_carriage_clearance_closed_mm':shoe_clearance,
            'pad_backing_volume_mm3':backed_volume,
            'gap_open_mm':base.opening(25, P), 'gap_closed_mm':base.opening(135, P)}


if __name__ == '__main__':
    import json
    data = parts()
    result = independent_jaw_requirements(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result['pass']:
        raise SystemExit(2)
