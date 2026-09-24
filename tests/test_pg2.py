import hashlib
import zipfile
from itertools import pairwise

import cadquery as cq
import pytest

from gripper_design.pg2 import import_archive, scan_pairs, slider_state


def _archive(tmp_path, *, corrupt=False, extra=None):
    archive = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("PG2_XL430/test.txt", b"changed" if corrupt else b"sample")
        target.writestr(
            "PG2_XL430/MANIFEST.sha256", hashlib.sha256(b"sample").hexdigest() + "  test.txt\n"
        )
        if extra:
            target.writestr(extra, "unsafe")
    return archive


def test_archive_integrity_and_no_overwrite(tmp_path):
    archive = _archive(tmp_path)
    destination = tmp_path / "imported"
    receipt = import_archive(archive, destination)
    assert receipt["verified_file_count"] == 1
    assert (destination / "PG2_XL430/test.txt").read_bytes() == b"sample"
    with pytest.raises(FileExistsError):
        import_archive(archive, destination)


@pytest.mark.parametrize(
    "extra", ["../escape", "/absolute", "PG2_XL430/../../escape", "PG2_XL430/unlisted"]
)
def test_archive_rejects_unsafe_or_unsealed_files(tmp_path, extra):
    with pytest.raises(ValueError):
        import_archive(_archive(tmp_path, extra=extra), tmp_path / "imported")
    assert not (tmp_path / "imported").exists()


def test_archive_rejects_corrupted_contents_before_extracting(tmp_path):
    with pytest.raises(ValueError, match="SHA"):
        import_archive(_archive(tmp_path, corrupt=True), tmp_path / "imported")
    assert not (tmp_path / "imported").exists()


def test_pg2_link_closure_symmetry_and_monotonic_opening():
    states = [slider_state(angle) for angle in range(30, 141)]
    # Donor START_HERE reports 50.81 mm (two decimal places).
    assert states[0]["opening_mm"] == pytest.approx(50.81, abs=0.005)
    assert states[-1]["opening_mm"] == pytest.approx(0.8)
    assert all(b["opening_mm"] < a["opening_mm"] for a, b in pairwise(states))
    assert max(s["link_closure_error_mm"] for s in states) < 1e-10


@pytest.mark.parametrize("angle", [29, 141, float("nan"), float("inf")])
def test_pg2_rejects_nonfinite_or_out_of_range_angle(angle):
    with pytest.raises(ValueError):
        slider_state(angle)


def test_pair_scan_covers_hardware_collisions_and_shells_without_skipping():
    box = cq.Workplane("XY").box(10, 10, 10).val()
    rows = scan_pairs(
        {"frame": box, "bolt": box, "shell": box.Shells()[0], "separate": box.translate((30, 0, 0))}
    )
    assert len(rows) == 6
    pair = next(r for r in rows if r["a"] == "frame" and r["b"] == "bolt")
    assert pair["status"] == "FAIL"
    assert pair["volume_mm3"] == pytest.approx(1000)
    assert any(r["status"] == "UNKNOWN" for r in rows)
