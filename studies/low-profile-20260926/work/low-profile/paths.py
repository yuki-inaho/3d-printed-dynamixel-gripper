"""Locate the imported study and its explicitly separate comparison snapshot."""

from pathlib import Path

STUDY = Path(__file__).resolve().parents[2]
REPO = next(p for p in STUDY.parents if (p / "gripper_design").is_dir())
PREVIOUS = STUDY.parent / "onshape-20260926"
OPTIMIZATION = PREVIOUS / "work/optimization"
COMPACT_STEP = PREVIOUS / "outputs/optimization-250g/CAD/Robot_250g_compact_D405.step"
