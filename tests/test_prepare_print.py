import json
import zipfile

import trimesh

from camera_jig.prepare_print import PARTS, check_gcode, check_project, mesh_report


def fixture():
    return """; total layer number: 10
G90
G21
M83
G28
M140 S60
M104 S220
M190 S60
M109 S220
G92 E0
G1 X20 Y20 Z0.2 E1
G1 X30 Y30 Z2 E1
M140 S0
M104 S0
M84 X Y E
; print_sequence = by layer
; enable_support = 1
"""


def test_gcode_normal_and_bad_controls():
    assert check_gcode(fixture())["pass"]
    for bad in ("M191 S40", "M600", "G1 X221 Y10", "M109 S280", "M25"):
        assert not check_gcode(fixture() + bad)["pass"]


def test_sequential_or_missing_shutdown_is_rejected():
    assert not check_gcode(fixture().replace("by layer", "by object"))["pass"]
    assert not check_gcode(fixture().replace("M104 S0", ""))["pass"]


def test_disconnected_or_open_print_part_fails():
    mesh = trimesh.creation.box()
    assert mesh_report(mesh)["pass"]
    shifted = mesh.copy()
    shifted.apply_translation([3, 0, 0])
    assert not mesh_report(trimesh.util.concatenate([mesh, shifted]))["pass"]
    mesh.update_faces(list(range(len(mesh.faces) - 1)))
    assert not mesh_report(mesh)["pass"]


def test_only_explicitly_reviewed_standard_pla_warning_is_accepted(tmp_path):
    path = tmp_path / "job.3mf"
    gcode = fixture() + "\n".join(f"; printing object {p}.stl id:1" for p in PARTS)

    def project(warning):
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("3D/3dmodel.model", "<model><build><item/><item/><item/></build></model>")
            z.writestr(
                "Metadata/plate_1.json",
                json.dumps(
                    {
                        "bbox_objects": [{"name": f"{p}.stl"} for p in PARTS],
                        "is_seq_print": False,
                        "nozzle_diameter": 0.4,
                        "bbox_all": [10, 10, 100, 100],
                        "bed_type": "hot_plate",
                    }
                ),
            )
            z.writestr(
                "Metadata/model_settings.config", '<config><mesh_stat edges_fixed="0"/></config>'
            )
            z.writestr("Metadata/slice_info.config", f"<config><plate>{warning}</plate></config>")
            z.writestr(
                "Metadata/project_settings.config",
                json.dumps(
                    {
                        "filament_type": ["PLA"],
                        "temperature_vitrification": ["60"],
                        "hot_plate_temp": ["60"],
                        "hot_plate_temp_initial_layer": ["60"],
                    }
                ),
            )

    known = '<warning msg="bed_temperature_too_high_than_filament" error_code="1000C001"/>'
    project(known)
    assert not check_project(path, gcode)["pass"]
    assert check_project(path, gcode, review_standard_pla_bed_warning=True)["pass"]
    assert not check_project(
        path, gcode.replace("M140 S60", "M140 S65"), review_standard_pla_bed_warning=True
    )["pass"]
    project(known + '<warning msg="floating_region"/>')
    assert not check_project(path, gcode, review_standard_pla_bed_warning=True)["pass"]
