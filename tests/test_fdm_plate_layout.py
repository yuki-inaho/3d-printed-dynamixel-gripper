"""Small G-code fixtures for the reusable plate comparison tool."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/fdm-plate-layout/scripts/compare_gcode.py"
SPEC = importlib.util.spec_from_file_location("compare_gcode", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
compare_gcode = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compare_gcode)


def gcode(tmp_path: Path, toolpaths: str) -> Path:
    path = tmp_path / "arc.gcode"
    path.write_text(
        "; estimated printing time (normal mode) = 1m 00s\n"
        "; filament used [cm3] = 1.0\n"
        "; printing object part.stl id:0 copy 0\n"
        "G90\nM83\nG1 X10 Y10 Z0.2\n" + toolpaths
    )
    return path


def test_arc_extrusion_counts_and_preserves_curved_bounds(tmp_path: Path) -> None:
    path = gcode(
        tmp_path,
        ";TYPE:Perimeter\n"
        "G3 X20 Y10 I5 J0 E1\n"
        "G3 X10 Y10 I-5 J0 E1\n"
        ";TYPE:Support material\n"
        "G2 X20 Y10 I5 J0 E0.5\n",
    )

    data = compare_gcode.parse(path)
    part = data["objects"]["part.stl"]

    assert data["arc_commands"] == 3
    assert part["body_e_mm"] == pytest.approx(2)
    assert part["support_e_mm"] == pytest.approx(0.5)
    assert min(y for _, y in part["body_points"]) == pytest.approx(5)
    assert max(y for _, y in part["body_points"]) == pytest.approx(15)
    assert any(is_support for _, is_support in part["first_layer"])


def test_full_circle_is_not_treated_as_stationary(tmp_path: Path) -> None:
    path = gcode(tmp_path, ";TYPE:Perimeter\nG2 X10 Y10 I5 J0 E1\n")

    part = compare_gcode.parse(path)["objects"]["part.stl"]

    assert part["body_e_mm"] == pytest.approx(1)
    assert len(part["body_points"]) > 30
    assert max(x for x, _ in part["body_points"]) == pytest.approx(20)


def test_unsupported_arc_form_fails_explicitly(tmp_path: Path) -> None:
    path = gcode(tmp_path, ";TYPE:Perimeter\nG2 X20 Y10 R5 E1\n")

    with pytest.raises(ValueError, match="require I/J"):
        compare_gcode.parse(path)


def test_moves_after_object_end_are_not_attributed_to_part(tmp_path: Path) -> None:
    path = gcode(
        tmp_path,
        ";TYPE:Perimeter\n"
        "G1 X20 Y10 E1\n"
        "; stop printing object part.stl id:0 copy 0\n"
        "G1 X30 Y10 E5\n",
    )

    part = compare_gcode.parse(path)["objects"]["part.stl"]

    assert part["body_e_mm"] == pytest.approx(1)
    assert max(x for x, _ in part["body_points"]) == pytest.approx(20)
