"""Compare known rigid transforms; periodic-face seams are not physical edges.

This is a consistency check for independently placed copies of the SAME source
part, not a proof of equivalence for arbitrary unrelated CAD solids.
"""
import numpy as np
import cadquery as cq
from scipy.spatial import cKDTree
from design import bounds


def compare(a, b, tol=1e-6):
    av = np.array([v.toTuple() for v in a.Vertices()])
    bv = np.array([v.toTuple() for v in b.Vertices()])
    vertex_err = max(cKDTree(bv).query(av)[0].max(),
                     cKDTree(av).query(bv)[0].max())

    def faces(s):
        return sorted((f.geomType(), *(round(x, 6) for x in
                       (*f.Center().toTuple(), f.Area(), *bounds(f))))
                      for f in s.Faces())

    face_match = faces(a) == faces(b)
    relative_volume = abs(a.Volume()-b.Volume())/max(a.Volume(), 1e-9)
    same_counts = (len(a.Vertices()) == len(b.Vertices()) and
                   len(a.Faces()) == len(b.Faces()))
    err = float(vertex_err)
    method = 'matching_vertices_and_face_descriptors'
    # A rotated circular washer has the same material boundary, but its arbitrary
    # cylindrical parameter seam moves. Compare to the boundary SHELL, never to
    # the solid interior, only after all surface descriptors already match.
    if err >= tol and face_match and same_counts and relative_volume < 1e-8:
        def directed(vertices, other):
            shells = other.Shells()
            if not shells:
                raise ValueError('Boundary shells unavailable; cannot verify')
            return max(min(cq.Vertex.makeVertex(*v).distance(s) for s in shells)
                       for v in vertices)
        err = float(max(directed(av, b), directed(bv, a)))
        method = 'periodic_seam_vertices_on_matching_boundary_shells'
    ok = same_counts and err < tol and relative_volume < 1e-8 and face_match
    return dict(pass_=bool(ok), max_vertex_distance_mm=err,
                vertex_coordinate_error_mm=float(vertex_err),
                relative_volume_difference=float(relative_volume),
                face_inventory_matches=face_match, method=method)
