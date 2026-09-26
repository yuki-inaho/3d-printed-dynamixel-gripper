"""Re-evaluate both depth imagers with complete physical support geometry."""

import json

from compare import candidate_spec
from design import extended_arm, load_source
from paths import COMPACT_STEP
from study import OUT, SIZE, cube, pose, save, screen, view_metrics

from gripper_design.camera_overhead_d405_r5 import build
from gripper_design.camera_overhead_r4 import retained_at
from scripts.assembly_io import read_step
from scripts.camera_view_d405_r5 import cases
from scripts.camera_view_r4 import View


def main():
    row = json.loads((OUT / "reports/selection.json").read_text())
    source = load_source()
    compact = {r.name: r.world for r in read_step(COMPACT_STEP)[2] if r.name.startswith("CAM5_")}
    groups = [
        ("compact75", 0, source, compact, pose([-0.2, 185, 250], 75)),
        (
            "low_profile30",
            row["extension_mm"],
            extended_arm(source, row["extension_mm"]),
            build(candidate_spec(row)),
            row["pose"],
        ),
    ]
    folder = OUT / "images/camera"
    folder.mkdir(parents=True, exist_ok=True)
    report = {
        "camera_body_exclusion": "Depth origins inside nominal camera body; only CAM5_D405_BODY excluded, all support/cable included",
        "hfov": 84,
        "size": SIZE,
        "physical_camera_calibrated": False,
        "cases": [],
    }
    for variant, extension, arm, mount, p in groups:
        for label, angle, edge in cases():
            scene = retained_at(arm, angle) | {
                n: s for n, s in mount.items() if n != "CAM5_D405_BODY"
            }
            if edge:
                scene["DIAGNOSTIC_CUBE"] = cube(edge, extension)
            view = View(scene, (0, 0, 0), (0, 1, 0), (0, 0, 1), 84, SIZE)
            for side in ["left", "right"]:
                image = folder / f"{variant}_{label}_{side}.png"
                metric = view_metrics(view, p, side, image)
                frustum = next(
                    (x for x in screen(p, extension) if x["edge"] == edge and x["side"] == side),
                    None,
                )
                passed = (
                    None
                    if edge is None
                    else (
                        metric["cube"]["visible_fraction"] >= 0.9
                        and frustum["inside"]
                        and frustum["min_depth_mm"] >= 75
                    )
                )
                report["cases"].append(
                    {
                        "variant": variant,
                        "case": label,
                        "angle": angle,
                        "edge": edge,
                        "side": side,
                        "metrics": metric,
                        "frustum": frustum,
                        "target_pass": passed,
                        "image": str(image.relative_to(OUT)),
                    }
                )
            view.close()
            save("full-optics.json", report)
            print(
                variant,
                label,
                [x["target_pass"] for x in report["cases"][-2:]],
                flush=True,
            )
    targets = [r for r in report["cases"] if r["variant"] == "low_profile30" and r["edge"]]
    report["selected_pass"] = all(r["target_pass"] for r in targets)
    report["selected_min_visibility"] = min(
        r["metrics"]["cube"]["visible_fraction"] for r in targets
    )
    report["selected_min_axial_depth_mm"] = min(r["frustum"]["min_depth_mm"] for r in targets)
    report["720p_100mm_depth_pass"] = report["selected_min_axial_depth_mm"] >= 100
    save("full-optics.json", report)
    print({k: v for k, v in report.items() if k != "cases"}, flush=True)
    if not report["selected_pass"]:
        raise RuntimeError("Selected physical camera scene fails target optics")


if __name__ == "__main__":
    main()
