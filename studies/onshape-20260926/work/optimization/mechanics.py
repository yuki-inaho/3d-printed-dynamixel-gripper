"""Explicit-unit gravity and camera geometry helpers; no motor safety rating."""

import math

import numpy as np

G = 9.80665


def moment(points_mm, masses_kg, origin_mm=(0, 0, 0)):
    r = (np.asarray(points_mm, float) - np.asarray(origin_mm)) / 1000
    f = np.zeros_like(r)
    f[:, 2] = -G * np.asarray(masses_kg)
    return np.cross(r, f).sum(axis=0)


def orient(direction):
    d = np.asarray(direction, float)
    d = d / np.linalg.norm(d)
    right = np.cross(d, [0, 0, 1])
    if np.linalg.norm(right) < 1e-8:
        raise ValueError("Vertical view needs an explicit roll reference")
    right /= np.linalg.norm(right)
    up = np.cross(right, d)
    return right, up, d


def project_points(points, eye, direction, up, hfov=84, size=(848, 480)):
    delta = np.asarray(points) - np.asarray(eye)
    d = np.asarray(direction)
    right = np.cross(d, up)
    depth = delta @ d
    th = math.tan(math.radians(hfov) / 2)
    tv = th * size[1] / size[0]
    inside = (
        (depth > 0)
        & (abs(delta @ right) <= depth * th)
        & (abs(delta @ up) <= depth * tv)
    )
    return inside, depth


def depth_ok(depth_mm, resolution):
    return bool(depth_mm >= {"848x480": 70, "1280x720": 100}[resolution])


def beam(force_n, length_mm, width_mm, height_mm, modulus_mpa):
    inertia = width_mm * height_mm**3 / 12
    stress_mpa = force_n * length_mm * height_mm / (2 * inertia)
    deflection_mm = force_n * length_mm**3 / (3 * modulus_mpa * inertia)
    return stress_mpa, deflection_mm
