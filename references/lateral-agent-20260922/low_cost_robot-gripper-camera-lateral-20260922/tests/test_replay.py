"""TDD tests for the pose-replay regression harness (scripts/replay_poses.py).

Run: uv run --group sim --group dev pytest -q tests/test_replay.py

These pin the DOF / workspace regression behaviour (DoD C-C3 / C-C4):
  - test_harness_finds_reference_set : baseline (XL330) yields a non-empty reachable,
                                       collision-free reference set (harness works).
  - test_harness_detects_collision   : a known self-collision pose returns ok=False
                                       (CONTROL — the harness actually detects defects,
                                       so a "pass" is meaningful, not vacuous).
  - test_xl430_proxy_preserves_open_poses : collision-free, NON-tightly-folded baseline
                                       poses stay collision-free + reachable on the
                                       XL430-proxy model (the workspace that survives).
  - test_xl430_proxy_loses_tight_fold : a tight-fold baseline-reachable pose IS lost on
                                       the XL430 proxy (xl430proxy_joint4 vs joint2) —
                                       this PINS the measured C-C4 workspace reduction so
                                       it cannot silently regress or be glossed as "0 loss".

scripts/ is not a package; inject it on sys.path.

KNOWN FINDING (C-C4, honest, no fallback): with the NAIVE axis-aligned XL430 collision
proxy, a 5^5 grid measured 461/2001 = ~23%% of baseline collision-free poses lost, 451
of them the joint4-proxy-vs-joint2 tight fold (the box long axis 46.5 pointed along Y,
over-extending toward the shoulder). CF-7 (2026-06-12) ORIENTED the proxy boxes so each
servo output shaft aligns with its joint axis (joint4 = Rz-90deg moves the 46.5 length
to X; joint5 = Ry+90deg; joint3 = identity); re-running the same 5^5 reference set then
measured 364/2001 = 18.2%% lost (1637 kept) -> an improvement (97 fewer losses), with
joint4-vs-joint2 still dominant (360). The tight fold below is STILL lost on the oriented
proxy, so this pin keeps its meaning (the loss is real, not glossed as "0"). New numbers:
temp/replay_xl430_oriented.json; naive: temp/replay_xl430.json. A faithful XL430 mesh
(further refinement) is out of this step's scope.
"""
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_BASELINE = _REPO / "simulation/low_cost_robot/scene.xml"
_PROXY = _REPO / "temp/sim_xl430proxy/scene_xl430proxy.xml"

mujoco = pytest.importorskip("mujoco")
import replay_poses as rp  # noqa: E402


def _model(path):
    return mujoco.MjModel.from_xml_path(str(path.resolve()))


# "Open" poses: baseline-reachable, NOT a tight joint4/joint2 fold -> survive the swap.
# (verified: baseline ok AND proxy ok). joint5 range [-2.45, 0.032].
_OPEN_POSES = [
    [0.0, 0.0, 0.0, 0.0, -1.2],
    [0.8, -0.8, 0.8, 0.0, -1.2],
    [-0.8, -0.8, 0.0, 0.0, -0.6],
]
# A tight fold: baseline-reachable & collision-free, but the enlarged joint4 servo hits
# joint2 -> lost on the proxy. This pins the measured C-C4 workspace reduction.
_TIGHT_FOLD = [-0.8, 0.8, -0.8, 0.8, -0.6]


def test_harness_finds_reference_set():
    """Baseline yields a non-empty reachable, collision-free reference set."""
    m = _model(_BASELINE)
    out = rp.run(_BASELINE, rp.grid_poses(m), settle_s=1.5)
    assert out["n_poses"] == 243            # 3^5 grid
    assert out["n_ok"] > 0                  # some poses are reachable & collision-free
    assert len(out["targets_ok"]) == out["n_ok"]


def test_harness_detects_collision():
    """CONTROL: a known self-collision pose (all joints near their extremes, where the
    XL330 arm already self-collides) must come back ok=False — proving the harness
    detects collisions, so a clean result elsewhere is not a false negative."""
    out = rp.run(_BASELINE, [[3.0, 3.0, 3.0, 3.0, -2.0]], settle_s=1.5)
    r = out["poses"][0]
    assert not r["ok"], f"expected a defect at the extreme pose: {r}"
    # it is detected as self-collision (not merely a tracking failure)
    assert r["self_interference_mm"] > rp.PENETRATION_LIMIT_MM or not r["reachable"]


@pytest.mark.skipif(not _PROXY.exists(), reason="XL430-proxy model not built")
def test_xl430_proxy_preserves_open_poses():
    """C-C3 / C-C4 (the surviving workspace): collision-free, non-tightly-folded
    baseline poses must stay collision-free AND reachable on the XL430 proxy."""
    base = rp.run(_BASELINE, _OPEN_POSES, settle_s=2.0)
    ref = [r["target"] for r in base["poses"] if r["ok"]]
    assert ref, "open subset produced no baseline-reachable poses to regress"
    proxy = rp.run(_PROXY, ref, settle_s=2.0)
    lost = [r for r in proxy["poses"] if not r["ok"]]
    assert not lost, ("XL430 proxy lost an OPEN baseline-reachable pose: "
                      + "; ".join(f"{r['target']} self={r['self_interference_mm']}mm "
                                  f"pair={r['self_pair']} reach={r['reachable']}"
                                  for r in lost))
    assert proxy["worst_self_interference_mm"] <= rp.PENETRATION_LIMIT_MM


@pytest.mark.skipif(not _PROXY.exists(), reason="XL430-proxy model not built")
def test_xl430_proxy_loses_tight_fold():
    """C-C4 (the measured loss): a tight-fold pose that the XL330 arm reaches
    collision-free is LOST on the XL430 proxy (xl430proxy_joint4 vs joint2). Pinning
    this prevents the regression from being silently reported as "0 loss"."""
    base = rp.run(_BASELINE, [_TIGHT_FOLD], settle_s=2.0)
    assert base["poses"][0]["ok"], "control pose must be baseline-reachable & collision-free"
    proxy = rp.run(_PROXY, [_TIGHT_FOLD], settle_s=2.0)
    r = proxy["poses"][0]
    assert not r["ok"], f"expected the tight fold to be lost on the XL430 proxy: {r}"
    assert r["reachable"], "loss is a NEW self-collision, not a tracking failure"
    assert r["self_interference_mm"] > rp.PENETRATION_LIMIT_MM
    assert "xl430proxy_joint4" in (r["self_pair"] or []), \
        f"expected the joint4 proxy to be the culprit, got {r['self_pair']}"
