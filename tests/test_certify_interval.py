"""Soundness and efficiency of the Lipschitz clearance certifier (no CAD needed)."""

import math
import random
from itertools import pairwise

import pytest

from scripts.review_pg3_motion_clearance import EPSILON_MM, certify_interval

SPEED = 19.027293925217254  # PG3 carriage point-speed bound, mm/rad
LOW, HIGH = math.radians(25), math.radians(135)


def test_touch_between_samples_is_never_certified():
    # Steepest admissible function reaching zero at a point no bisection hits exactly.
    t0 = LOW + (HIGH - LOW) / math.pi
    result = certify_interval(lambda t: SPEED * abs(t - t0), SPEED, LOW, HIGH, max_checks=4096)
    assert result["status"] == "UNPROVEN"


def test_positive_minimum_between_samples_is_certified():
    t0 = LOW + (HIGH - LOW) / math.pi
    result = certify_interval(
        lambda t: SPEED * abs(t - t0) + 3 * EPSILON_MM, SPEED, LOW, HIGH, max_checks=4096
    )
    assert result["status"] == "PROVEN_CLEAR"


@pytest.mark.parametrize("seed", range(200))
def test_random_lipschitz_functions_are_never_falsely_certified(seed):
    rng = random.Random(seed)
    knots = sorted(rng.uniform(LOW, HIGH) for _ in range(rng.randint(2, 12)))
    xs = [LOW, *knots, HIGH]
    ys = [rng.uniform(-0.2, 1.0)]
    for a, b in pairwise(xs):  # slopes bounded by SPEED keep the function admissible
        ys.append(ys[-1] + rng.uniform(-SPEED, SPEED) * (b - a))

    def value(t):
        for (a, ya), (b, yb) in pairwise(zip(xs, ys)):
            if a <= t <= b:
                return max(0.0, ya + (yb - ya) * (t - a) / (b - a))
        raise AssertionError(t)

    true_min = min(max(0.0, y) for y in ys)  # piecewise-linear minimum is at a knot
    result = certify_interval(value, SPEED, LOW, HIGH, max_checks=4096)
    if result["status"] == "PROVEN_CLEAR":
        assert true_min > 0


def test_constant_running_gap_needs_about_one_check_per_covered_width():
    # The guide-relief case: a constant 0.3 mm gap along the whole stroke.
    result = certify_interval(lambda t: 0.3, SPEED, LOW, HIGH)
    assert result["status"] == "PROVEN_CLEAR"
    covered_width = 2 * (0.3 - 2 * EPSILON_MM) / SPEED
    assert result["checks"] <= 1.1 * math.ceil((HIGH - LOW) / covered_width)


def test_reused_distance_matches_cadquery_distance_including_contact_and_overlap():
    import cadquery as cq

    from scripts.review_pg3_motion_clearance import DistanceTo

    fixed = cq.Workplane().box(20, 10, 10).faces(">Z").workplane().hole(4).val()
    moving = cq.Workplane().cylinder(8, 1.5).val()
    measure = DistanceTo(fixed)
    # separated, touching, inside the hole, overlapping material, and far away
    for offset in [(0, 0, 12), (0, 0, 9), (0, 0, 0), (6, 0, 0), (40, 3, -2), (10, 0, 0)]:
        placed = moving.translate(offset)
        assert measure(placed) == fixed.distance(placed), offset
