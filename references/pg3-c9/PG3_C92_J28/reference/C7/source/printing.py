"""Final print orientation, separate from assembly coordinates.
Carriages: back on bed, preserving the sliding shoes' flat lower faces.
Support only beneath the raised pivot boss/web; keep the sliding tracks unscarred.
"""
from design import print_orientation as candidate_orientation,bounds

def print_orientation(name,shape):
    if name.startswith('03_carriage') or name.startswith('04_carriage'):
        b=bounds(shape)
        return shape.translate((-(b[0]+b[3])/2,-(b[1]+b[4])/2,-b[2]))
    return candidate_orientation(name,shape)
