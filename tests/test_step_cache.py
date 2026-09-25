"""The STEP row cache must be indistinguishable from a fresh parse (and fail safe)."""

import cadquery as cq
import pytest

from scripts.assembly_io import bounds, read_step
from scripts.step_cache import CACHE_ENV, read_rows


@pytest.fixture
def assembly_step(tmp_path):
    """Two placements of one shared box, a colored copy, and a nested cylinder."""
    box = cq.Workplane().box(10, 20, 5).val()
    asm = cq.Assembly(name="root")
    # Same shape and no color: the STEP keeps one prototype for both instances.
    asm.add(box, name="box_a", loc=cq.Location((5, 0, 0), (0, 0, 1), 30))
    asm.add(box, name="box_b", loc=cq.Location((-40, 7, 3)))
    asm.add(box, name="box_red", loc=cq.Location((0, -30, 0)), color=cq.Color(1, 0, 0, 1))
    sub = cq.Assembly(name="sub", loc=cq.Location((0, 50, 0), (1, 0, 0), 90))
    sub.add(cq.Workplane().cylinder(12, 4).val(), name="pin", color=cq.Color(0, 0, 1, 1))
    asm.add(sub)
    path = tmp_path / "asm.step"
    asm.export(str(path))
    return path


def _signature(rows):
    out = []
    for r in rows:
        w = r.world
        color = None if r.color is None else tuple(round(c, 12) for c in r.color.toTuple())
        out.append((r.index, r.path, r.name, color, [round(v, 9) for v in bounds(w)], round(w.Volume(), 9)))
    return out


def _sharing(rows):
    return [[a.shape.wrapped.IsPartner(b.shape.wrapped) for b in rows] for a in rows]


def test_cached_rows_match_fresh_parse(assembly_step, tmp_path, monkeypatch):
    fresh = read_step(assembly_step)[2]
    monkeypatch.setenv(CACHE_ENV, str(tmp_path / "cache"))
    cold = read_rows(assembly_step)
    warm = read_rows(assembly_step)
    assert len(fresh) == 4
    assert _signature(cold) == _signature(fresh)
    assert _signature(warm) == _signature(fresh)
    # Sub-shape sharing is reproduced exactly, and the fixture really has a shared pair.
    assert _sharing(warm) == _sharing(fresh)
    names = [r.name for r in fresh]
    assert _sharing(fresh)[names.index("box_a")][names.index("box_b")]
    assert all(r.label is None for r in warm)


def test_without_cache_env_read_rows_is_read_step(assembly_step, monkeypatch):
    monkeypatch.delenv(CACHE_ENV, raising=False)
    assert _signature(read_rows(assembly_step)) == _signature(read_step(assembly_step)[2])


def test_changed_file_is_reparsed(assembly_step, tmp_path, monkeypatch):
    monkeypatch.setenv(CACHE_ENV, str(tmp_path / "cache"))
    before = read_rows(assembly_step)
    replacement = cq.Assembly(name="root")
    replacement.add(cq.Workplane().sphere(3).val(), name="ball")
    replacement.export(str(assembly_step))
    after = read_rows(assembly_step)
    assert [r.name for r in before] != [r.name for r in after] == ["ball"]


def test_mesh_on_a_served_shape_does_not_leak_into_later_reads(assembly_step, tmp_path, monkeypatch):
    monkeypatch.setenv(CACHE_ENV, str(tmp_path / "cache"))
    first = read_rows(assembly_step)
    exact = [r.world.BoundingBox().zlen for r in read_rows(assembly_step)]
    for r in first:
        r.world.tessellate(2.0, 2.0)  # coarse mesh inflates mesh-based bounding boxes
    again = [r.world.BoundingBox().zlen for r in read_rows(assembly_step)]
    assert again == exact


def test_truncated_or_altered_cache_is_rebuilt_not_trusted(assembly_step, tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setenv(CACHE_ENV, str(cache))
    reference = _signature(read_rows(assembly_step))
    (brep,) = cache.glob("*.brep")
    data = brep.read_bytes()
    brep.write_bytes(data[: len(data) // 2])  # truncated
    assert _signature(read_rows(assembly_step)) == reference
    data = bytearray(brep.read_bytes())
    data[len(data) // 2] ^= 0x01  # one flipped bit that may still parse
    brep.write_bytes(bytes(data))
    assert _signature(read_rows(assembly_step)) == reference
    assert brep.read_bytes() != bytes(data)  # the entry was rewritten
