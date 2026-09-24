import math

import cadquery as cq
import pytest

from camera_jig.build import (
    ROOT,
    build_parts,
    collision_rows,
    common_volume,
    export,
    validate_change_mask,
    validate_parts,
)
from camera_jig.spec import SPEC, validate_camera_mount_spec


@pytest.fixture(scope="module")
def parts():
    return build_parts()


def test_parts_are_valid_single_positive_solids(parts):
    for shape in parts.values():
        assert shape.isValid()
        assert len(shape.Solids()) == 1
        assert shape.Volume() > 0


def test_camera_mount_parent_is_p05():
    validate_camera_mount_spec(SPEC.raw)
    invalid = dict(SPEC.raw)
    invalid["parent"] = dict(SPEC.parent, part="J5_output_horn")
    with pytest.raises(ValueError, match="P05"):
        validate_camera_mount_spec(invalid)


def test_camera_mount_change_mask_preserves_source_p05(parts):
    result = validate_change_mask(parts)
    assert result["pass"]
    assert result["source_mutated"] is False
    assert max(result["source_intersections_mm3"].values()) < 1e-5

    link = cq.importers.importStep(str(ROOT / "references/arm-r3/P05_wrist_XL430.step")).val()
    invalid = validate_change_mask(dict(parts, saddle=link))
    assert not invalid["pass"]
    assert invalid["source_intersections_mm3"]["saddle"] > 1


def test_export_refuses_to_overwrite_existing_run(tmp_path):
    existing = tmp_path / "existing-run"
    existing.mkdir()
    with pytest.raises(FileExistsError):
        export(existing)


def test_camera_pattern_is_measured_from_exported_geometry(parts, tmp_path):
    path = tmp_path / "camera_carrier.step"
    cq.exporters.export(parts["camera_carrier"], str(path))
    actual = dict(parts, camera_carrier=cq.importers.importStep(str(path)).val())
    result = validate_parts(actual)
    assert result["camera_hole_count"] == 4
    assert result["camera_pattern_max_error_mm"] < 1e-5
    assert result["camera_diameter_error_mm"] < 1e-5
    assert result["contact_area_pass"]
    assert result["contact_area_probe_mm2"]["camera_carrier_to_saddle"] > 100
    assert result["geometry_pass"]


def test_wrong_camera_pattern_fails():
    result = validate_parts(build_parts(camera_pitch=26))
    assert not result["geometry_pass"]
    assert result["camera_pattern_max_error_mm"] == pytest.approx(math.sqrt(2))


def test_original_link_is_not_cut(parts):
    link = cq.importers.importStep(str(ROOT / "references/arm-r3/P05_wrist_XL430.step")).val()
    for shape in parts.values():
        assert common_volume(shape, link) < 1e-5


def test_front_jaw_forced_into_link_is_rejected(parts):
    result = validate_parts(dict(parts, front_jaw=parts["front_jaw"].translate((0, -1, 0))))
    assert result["link_intersections_mm3"]["front_jaw"] > 1
    assert not result["geometry_pass"]


def test_unverified_physical_fit_never_becomes_release(parts):
    result = validate_parts(parts)
    assert not result["fabrication_approved"]
    assert result["physical_link_dimensions"] == "unknown"
    assert result["motion_clearance"] == "not_checked"


def test_boolean_controls():
    box = cq.Workplane("XY").box(2, 2, 2).val()
    assert common_volume(box, box.copy()) == pytest.approx(8)
    assert common_volume(box, box.translate((5, 0, 0))) == pytest.approx(0)


def test_disconnected_saddle_is_rejected(parts):
    orphan = cq.Workplane("XY").box(1, 1, 1).val().translate((300, 0, 0))
    broken = cq.Compound.makeCompound([parts["saddle"], orphan])
    result = validate_parts(dict(parts, saddle=broken))
    assert result["part_solids"]["saddle"] == 2
    assert not result["geometry_pass"]


def test_surface_obstacle_is_not_silently_ignored():
    shell = cq.Workplane("XY").box(4, 4, 4).val().Shells()[0]
    inside = cq.Workplane("XY").box(1, 1, 1).val()
    hits, errors = collision_rows({"part": inside}, {"shell": shell})
    assert not hits
    assert errors and "not proven separated" in errors[0]["error"]


def test_surface_obstacle_enclosing_box_proves_clearance():
    shell = cq.Workplane("XY").box(4, 4, 4).val().Shells()[0]
    # Two disconnected legs surround the box in X but do not touch it.
    leg = cq.Workplane("XY").box(1, 1, 1).val()
    part = cq.Compound.makeCompound([leg.translate((-4, 0, 0)), leg.translate((4, 0, 0))])
    evidence = []
    assert collision_rows({"part": part}, {"shell": shell}, non_solid_evidence=evidence) == ([], [])
    assert evidence[0]["distance_mm"] == pytest.approx(1.5 - 1e-5)


def test_nominal_screw_stack_detects_short_screw():
    from camera_jig.serviceability import screw_stack

    assert screw_stack(10, 6.5, 1.6, 0.4)["nominal_full_nut_and_one_thread"]
    assert not screw_stack(8, 6.5, 1.6, 0.4)["nominal_full_nut_and_one_thread"]
    assert not screw_stack(10, 6.5, 1.6, 0.4)["purchase_spec_confirmed"]


def test_reference_camera_and_spacer_really_have_28mm_pattern():
    from cadre.probes import cylinder_surface_sense
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    from camera_jig.build import donor_parts

    spacer, camera = donor_parts()
    for shape, axes, radius in ((spacer, (0, 1), 1.1), (camera, (0, 2), 1.25)):
        centers = set()
        for face in shape.Faces():
            if face.geomType() != "CYLINDER" or cylinder_surface_sense(face) != "concave":
                continue
            c = BRepAdaptor_Surface(face.wrapped).Cylinder()
            if abs(c.Radius() - radius) < 1e-6:
                p = c.Location()
                xyz = (p.X(), p.Y(), p.Z())
                centers.add(tuple(round(xyz[i], 5) for i in axes))
        assert {(-14, -14), (-14, 14), (14, -14), (14, 14)} <= centers


def test_nominal_nut_tool_has_clearance_for_bolt_tail():
    from camera_jig.build import envelope_hardware
    from camera_jig.serviceability import tools

    hardware = envelope_hardware()
    for prefix, length, count in (("M2", 10, 4), ("M3", 16, 2)):
        for i in range(count):
            assert (
                common_volume(
                    tools()[f"{prefix}_{i}_nut"], hardware[f"{prefix}x{length}_{i}_ENVELOPE"]
                )
                < 1e-5
            )


def test_carrier_fastener_tools_clear_candidate_parts(parts):
    from camera_jig.serviceability import tools

    carrier_tools = {name: shape for name, shape in tools().items() if name.startswith("M2C_")}
    hits, errors = collision_rows(carrier_tools, parts)
    assert not hits
    assert not errors
