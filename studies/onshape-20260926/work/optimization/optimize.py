"""Reproducible 250 g camera-mount trade study. All output goes to this task."""

import argparse
import hashlib
import itertools
import json
import math
from dataclasses import asdict, replace
from pathlib import Path

import cadquery as cq
import numpy as np
from gripper_design import camera_overhead_d405_r5 as r5
from gripper_design.camera_overhead_r4 import ANCHORS, TOP, box, retained_at
from mechanics import G, beam, depth_ok, moment, orient, project_points
from scripts.assembly_io import bounds, read_step
from scripts.build_camera_overhead_d405_r5 import color
from scripts.camera_view_d405_r5 import cases
from scripts.camera_view_r4 import View
from scripts.render_cad import render
from scripts.validate_camera_overhead_r4 import box_distance

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/optimization-250g"
SOURCE = r5.RUN / "CAD/ID5_D405_mid_ASSEMBLY.step"
CENTER = np.array([-0.2, 214.6, 164.6])
WRIST = np.array([-0.2, 104.9, 164.6])
SHOULDER = np.array([-0.2, 0, 56.3])
SIZE = (848, 480)


def save(name, data):
    (OUT / "reports" / name).write_text(json.dumps(data, indent=2))


def source():
    rows = read_step(SOURCE)[2]
    assert len(rows) == len({r.name for r in rows}) == 257
    return {r.name: r.world for r in rows}


def corners(edge):
    return np.array(list(itertools.product([-edge / 2, edge / 2], repeat=3))) + CENTER


def pose(glass, pitch=None):
    g = np.asarray(glass, float)
    if pitch is None:
        right, up, d = orient(CENTER - g)
    else:
        d = np.array([0, math.cos(math.radians(pitch)), -math.sin(math.radians(pitch))])
        right, up, d = orient(d)
    return {
        "glass": g.tolist(),
        "direction": d.tolist(),
        "up": up.tolist(),
        "right": right.tolist(),
        "eyes": {
            k: (g - 3.7 * d + sign * 9 * right).tolist()
            for k, sign in [("left", -1), ("right", 1)]
        },
    }


def screen(p):
    d, up = p["direction"], p["up"]
    rows = []
    for edge in (10, 20, 30):
        for side, eye in p["eyes"].items():
            inside, dep = project_points(corners(edge), eye, d, up)
            rows.append(
                {
                    "edge": edge,
                    "side": side,
                    "all_in_frame": bool(inside.all()),
                    "min_depth_mm": float(min(dep)),
                    "depth_480p": depth_ok(min(dep), "848x480"),
                    "depth_720p": depth_ok(min(dep), "1280x720"),
                }
            )
    return rows


def view_metrics(view, p, side, image=None, cube_only=False):
    cam = view.renderer.GetActiveCamera()
    eye = np.array(p["eyes"][side])
    cam.SetPosition(eye)
    cam.SetFocalPoint(eye + np.array(p["direction"]) * 100)
    cam.SetViewUp(p["up"])
    if image:
        view.capture(image)
    actual = view.capture(seg=True)
    result = {}
    for label, names in {
        "cube": {"DIAGNOSTIC_CUBE"},
        "jaw_L": {"PG3_finger_L", "PG3_pad_L"},
        "jaw_R": {"PG3_finger_R", "PG3_pad_R"},
    }.items():
        if cube_only and label != "cube":
            continue
        names = names & view.ids.keys()
        if not names:
            continue
        codes = [view.ids[n] for n in names]
        reference = view.capture(seg=True, only=names)
        mask = np.isin(reference, codes)
        result[label] = {
            "projected_pixels": int(mask.sum()),
            "visible_fraction": float(
                (mask & np.isin(actual, codes)).sum() / mask.sum()
            )
            if mask.any()
            else 0,
            "touches_border": bool(
                mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any()
            ),
        }
    return result


def search():
    parts = source()
    arm = {n: s for n, s in parts.items() if not n.startswith("CAM5_")}
    rows = []
    for y, z, pitch in itertools.product(
        range(145, 200, 5), range(210, 260, 5), range(40, 85, 5)
    ):
        p = pose([-0.2, y, z], pitch)
        checks = screen(p)
        rows.append(
            {
                "id": f"C_y{y}_z{z}_p{pitch}",
                "kind": "central",
                "pitch": pitch,
                "pose": p,
                "screen": checks,
                "screen_pass": all(
                    c["all_in_frame"] and c["min_depth_mm"] >= 75 for c in checks
                ),
            }
        )
    for sign, x, y, z in itertools.product(
        (-1, 1), range(40, 100, 10), range(150, 205, 10), range(180, 245, 10)
    ):
        p = pose([-0.2 + sign * x, y, z])
        checks = screen(p)
        rows.append(
            {
                "id": f"S_x{sign * x}_y{y}_z{z}",
                "kind": "lateral_concept",
                "pose": p,
                "screen": checks,
                "screen_pass": all(
                    c["all_in_frame"] and c["min_depth_mm"] >= 75 for c in checks
                ),
            }
        )
    baseline = {
        "id": "R5",
        "kind": "baseline",
        "pitch": 65,
        "pose": pose(r5.Spec().glass_center, 65),
    }
    baseline["screen"] = screen(baseline["pose"])
    # Search optics with unchanged arm first. This is explicitly optimistic: no new support yet.
    central = sorted(
        (r for r in rows if r["kind"] == "central" and r["screen_pass"]),
        key=lambda r: (
            r["pose"]["glass"][2],
            np.linalg.norm(np.array(r["pose"]["glass"]) - WRIST),
            abs(
                r["pitch"]
                - math.degrees(
                    math.atan2(
                        r["pose"]["glass"][2] - CENTER[2],
                        CENTER[1] - r["pose"]["glass"][1],
                    )
                )
            ),
        ),
    )
    lateral = sorted(
        (r for r in rows if r["kind"] == "lateral_concept" and r["screen_pass"]),
        key=lambda r: (r["pose"]["glass"][2], abs(r["pose"]["glass"][0])),
    )

    # Cover distinct positions, not 20 tiny angular variants of one location.
    def diverse(items, count):
        chosen, seen = [], set()
        for r in items:
            g = tuple(r["pose"]["glass"])
            if g in seen:
                continue
            chosen.append(r)
            seen.add(g)
            if len(chosen) == count:
                break
        return chosen

    candidates = [baseline] + diverse(central, 110)
    for z in range(180, 245, 10):
        candidates += diverse([r for r in lateral if r["pose"]["glass"][2] == z], 10)
    for r in candidates:
        r["bare_optics"] = []
    for label, angle, edge in cases():
        if not edge:
            continue
        h = edge / 2
        scene = retained_at(arm, angle)
        scene["DIAGNOSTIC_CUBE"] = box(
            *(x for pair in zip(CENTER - h, CENTER + h) for x in pair)
        )
        view = View(scene, (0, 0, 0), (0, 1, 0), (0, 0, 1), 84, SIZE)
        for r in candidates:
            for side in ("left", "right"):
                metrics = view_metrics(view, r["pose"], side, cube_only=True)
                r["bare_optics"].append(
                    {"case": label, "side": side, "metrics": metrics}
                )
        view.close()
        print("bare optics completed", label, len(candidates), flush=True)
    for r in candidates:
        r["minimum_cube_visible"] = min(
            x["metrics"]["cube"]["visible_fraction"] for x in r["bare_optics"]
        )
        r["bare_optics_pass"] = r["minimum_cube_visible"] >= 0.9
        g = np.array(r["pose"]["glass"])
        r["camera_only_shoulder_M_Nm"] = moment([g], [0.058], SHOULDER).tolist()
        r["camera_only_wrist_worst_orientation_Nm"] = float(
            0.058 * G * np.linalg.norm((g - WRIST)[1:]) / 1000
        )
    save(
        "search.json",
        {
            "grid_count": len(rows),
            "screen_pass_count": sum(r["screen_pass"] for r in rows),
            "own_mount_in_bare_optics": False,
            "all_grid": rows,
            "rendered_candidates": candidates,
        },
    )
    print(
        "CENTRAL",
        [
            (r["id"], round(r["minimum_cube_visible"], 3))
            for r in candidates
            if r["kind"] == "central"
        ],
        flush=True,
    )
    print(
        "LATERAL",
        [
            (r["id"], round(r["minimum_cube_visible"], 3))
            for r in candidates
            if r["kind"] == "lateral_concept"
        ],
        flush=True,
    )


def selected():
    data = json.loads((OUT / "reports/selection.json").read_text())
    return data, replace(
        r5.Spec(),
        revision=data["id"],
        glass_center=tuple(data["pose"]["glass"]),
        pitch_deg=data["pitch"],
    )


def mass_report(mount):
    items = []
    for n, s in mount.items():
        if n in ("CAM5_BASE", "CAM5_D405_CARRIER"):
            mass = s.Volume() * 0.00124
            basis = "solid PLA 1.24 g/cm3"
        elif n == "CAM5_D405_BODY":
            mass = 58.0
            basis = "datasheet nominal +/-10%"
        elif n == "CAM5_D405_USB_PLUG":
            mass = 6.0
            basis = "assumed 6 g envelope, weigh actual cable"
        elif n == "CAM5_D405_USB_CABLE_STUB":
            mass = 1.0
            basis = "assumed 1 g short stub, excludes free cable"
        else:
            mass = s.Volume() * 0.00785
            basis = "nominal steel envelope 7.85 g/cm3"
        items.append(
            {
                "name": n,
                "mass_g": mass,
                "com_mm": list(s.Center().toTuple()),
                "basis": basis,
            }
        )
    masses = np.array([r["mass_g"] / 1000 for r in items])
    coms = np.array([r["com_mm"] for r in items])
    com = np.average(coms, axis=0, weights=masses)
    M_payload = {
        "mass_kg": 0.25,
        "com_mm": CENTER.tolist(),
        "wrist_M_Nm": moment([CENTER], [0.25], WRIST).tolist(),
        "shoulder_M_Nm": moment([CENTER], [0.25], SHOULDER).tolist(),
    }

    def both(origin):
        m = moment(coms, masses, origin)
        rel = (coms - origin) / 1000
        sy = float((masses * rel[:, 1]).sum())
        sz = float((masses * rel[:, 2]).sum())
        return {
            "reference_M_Nm": m.tolist(),
            "pitch_gravity_amplitude_Nm": G * math.hypot(sy, sz),
            "plus_payload_reference_M_Nm": (
                m + moment([CENTER], [0.25], origin)
            ).tolist(),
        }

    zmax = max(bounds(s)[5] for s in mount.values())
    return {
        "items": items,
        "mass_g": float(masses.sum() * 1000),
        "com_mm": com.tolist(),
        "printed_mass_g": sum(
            r["mass_g"] for r in items if r["basis"].startswith("solid PLA")
        ),
        "height_above_motor_top_mm": zmax - TOP,
        "wrist": both(WRIST),
        "shoulder": both(SHOULDER),
        "payload_only": M_payload,
        "full_arm_mass_included": False,
        "motor_continuous_rating_verified": False,
    }


def export():
    selection, s = selected()
    original = source()
    arm = {n: v for n, v in original.items() if not n.startswith("CAM5_")}
    mount = r5.build(s)
    for n in ("CAM5_BASE", "CAM5_D405_CARRIER"):
        assert (
            mount[n].isValid() and len(mount[n].Solids()) == 1 and mount[n].Volume() > 0
        ), n
    assembly = cq.Assembly(name="Robot_250g_compact_D405")
    for n, shape in (arm | mount).items():
        assembly.add(shape, name=n, color=cq.Color(*color(n)))
    path = OUT / "CAD/Robot_250g_compact_D405.step"
    assembly.save(str(path))
    for n in ("CAM5_BASE", "CAM5_D405_CARRIER"):
        cq.exporters.export(mount[n], str(OUT / "CAD" / f"{n}.step"))
        cq.exporters.export(
            mount[n],
            str(OUT / "CAD" / f"{n}.stl"),
            tolerance=0.05,
            angularTolerance=0.1,
        )
    reload = {r.name: r.world for r in read_step(path)[2]}
    errors = []
    for n, sh in (arm | mount).items():
        other = reload[n]
        if (
            abs(sh.Volume() - other.Volume()) > 0.01
            or max(abs(np.array(bounds(sh)) - bounds(other))) > 1e-4
        ):
            errors.append(n)
    assert len(reload) == 257 and not errors, (len(reload), errors)
    anchor_checks = []
    for x, y, z in ANCHORS:
        plug = cq.Solid.makeCylinder(1.3, 2, cq.Vector(x, y, z + 0.05))
        anchor_checks.append(abs(mount["CAM5_BASE"].intersect(plug).Volume()))
    assert max(anchor_checks) < 1e-5
    for name, parts in [("R5", original), ("compact", arm | mount)]:
        if (
            name == "R5"
            and (OUT / "images/R5_side.png").exists()
            and (OUT / "images/R5_assembly.png").exists()
        ):
            continue  # unchanged, hash-pinned input; preserve its existing reference renders
        render(
            [(sh, color(n)) for n, sh in parts.items()],
            OUT / "images" / f"{name}_assembly.png",
            direction=(1, -0.6, 0.5),
            focus=(-0.2, 140, 170),
            scale=165,
            size=(1200, 1000),
        )
        render(
            [(sh, color(n)) for n, sh in parts.items()],
            OUT / "images" / f"{name}_side.png",
            direction=(1, 0, 0),
            focus=(-0.2, 180, 214),
            scale=85,
            size=(1100, 900),
        )
    old = {n: sh for n, sh in original.items() if n.startswith("CAM5_")}
    save(
        "export.json",
        {
            "selection": selection,
            "spec": asdict(s),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "occurrences": len(reload),
            "roundtrip_errors": errors,
            "anchor_probe_overlap_mm3": anchor_checks,
            "screw_stack": r5.d405_stack(s),
            "baseline": mass_report(old),
            "candidate": mass_report(mount),
            "camera_glass_delta_mm": (
                np.array(s.glass_center) - r5.Spec().glass_center
            ).tolist(),
            "existing_urdf_matches_candidate": False,
        },
    )
    print("EXPORT PASS", len(reload), mass_report(mount)["mass_g"], flush=True)


def overlaps(first, second, same=False):
    result = []
    bb = {n: bounds(s) for n, s in second.items()}
    for n, s in first.items():
        ab = bounds(s)
        for m, t in second.items():
            if same and n >= m:
                continue
            if box_distance(ab, bb[m]) > 1e-6:
                continue
            if not s.Solids() or not t.Solids():
                # Supplier surfaces have no certified interior. A non-separated
                # bounding box is unresolved, even if nearest face is distant.
                result.append(
                    {
                        "a": n,
                        "b": m,
                        "gap_mm": s.distance(t),
                        "type": "surface_bbox_unresolved",
                    }
                )
                continue
            v = abs(s.intersect(t).Volume())
            if v > 1e-5:
                result.append({"a": n, "b": m, "volume_mm3": v, "type": "volume"})
    return result


def validate():
    from scripts.id4_sweep_d405_r5 import MOVING, id4_axis

    selection, _spec = selected()
    original = source()
    candidate = {
        r.name: r.world for r in read_step(OUT / "CAD/Robot_250g_compact_D405.step")[2]
    }
    arm = {n: v for n, v in original.items() if not n.startswith("CAM5_")}
    mounts = {
        "R5": {n: v for n, v in original.items() if n.startswith("CAM5_")},
        "compact": {n: v for n, v in candidate.items() if n.startswith("CAM5_")},
    }
    report = {
        "fov_h_deg": 84,
        "size": SIZE,
        "real_intrinsics_verified": False,
        "physical_strength_verified": False,
        "cases": [],
        "collisions": [],
    }
    for label, angle, edge in cases():
        bare = retained_at(arm, angle)
        for variant, mount in mounts.items():
            p = (
                pose(r5.Spec().glass_center, 65)
                if variant == "R5"
                else selection["pose"]
            )
            scene = bare | {n: v for n, v in mount.items() if n != "CAM5_D405_BODY"}
            if edge:
                h = edge / 2
                scene["DIAGNOSTIC_CUBE"] = box(
                    *(x for pair in zip(CENTER - h, CENTER + h) for x in pair)
                )
            view = View(scene, (0, 0, 0), (0, 1, 0), (0, 0, 1), 84, SIZE)
            for side in ("left", "right"):
                image = OUT / "images" / f"{variant}_{label}_{side}.png"
                met = view_metrics(view, p, side, image)
                for key, names in {
                    "jaw_L": ["PG3_finger_L", "PG3_pad_L"],
                    "jaw_R": ["PG3_finger_R", "PG3_pad_R"],
                    "cube": ["DIAGNOSTIC_CUBE"],
                }.items():
                    if key not in met:
                        continue
                    pts = np.array(
                        [
                            v.toTuple()
                            for n in names
                            for v in scene[n].tessellate(0.2, 0.3)[0]
                        ]
                    )
                    inside, dep = project_points(
                        pts, p["eyes"][side], p["direction"], p["up"]
                    )
                    met[key].update(
                        {
                            "vertex_fraction_in_frame": float(inside.mean()),
                            "min_depth_mm": float(min(dep)),
                            "depth_480p": depth_ok(min(dep), "848x480"),
                            "depth_720p": depth_ok(min(dep), "1280x720"),
                        }
                    )
                report["cases"].append(
                    {
                        "variant": variant,
                        "case": label,
                        "side": side,
                        "metrics": met,
                        "image": str(image.relative_to(OUT)),
                    }
                )
            view.close()
            if not edge:
                report["collisions"].append(
                    {
                        "variant": variant,
                        "case": label,
                        "mount_to_arm": overlaps(mount, bare),
                        "within_mount": overlaps(mount, mount, True),
                    }
                )
            save("validation.json", report)
            print("validate", variant, label, flush=True)
    upstream = {n: v for n, v in original.items() if not n.startswith(MOVING)}
    ub = {n: bounds(v) for n, v in upstream.items()}
    point, axis, _ = id4_axis(original)
    sweep = {}

    def conservative_hits(group, degrees):
        for n, shape in group.items():
            moved = (
                shape.rotate(tuple(point), tuple(point + axis), float(degrees))
                if degrees
                else shape
            )
            b = bounds(moved)
            for m, t in upstream.items():
                if box_distance(b, ub[m]) >= 0.3:
                    continue
                if not moved.Solids() or not t.Solids():
                    return [
                        {
                            "moving": n,
                            "upstream": m,
                            "status": "surface_bbox_unresolved",
                            "gap_mm": moved.distance(t),
                        }
                    ]
                vol = abs(moved.intersect(t).Volume())
                if vol > 1e-5 or moved.distance(t) < 0.3:
                    return [
                        {
                            "moving": n,
                            "upstream": m,
                            "status": "collision_or_gap_below_0.3mm",
                            "volume_mm3": vol,
                        }
                    ]
        return []

    def sample(group, sign):
        last = 0
        for deg in range(sign * 2, sign * 182, sign * 2):
            h = conservative_hits(group, deg)
            if h:
                return last, {"deg": deg, "first_hit": h[0]}
            last = deg
        return last, None

    for variant, mount in mounts.items():
        zero = conservative_hits(mount, 0)
        lo, lohit = sample(mount, -1)
        hi, hihit = sample(mount, 1)
        sweep[variant] = {
            "free_interval_deg": [lo, hi],
            "negative_stop": lohit,
            "positive_stop": hihit,
            "hits_at_zero": zero,
        }
    report["mount_sweep"] = sweep
    report["sweep_step_deg"] = 2
    report["continuous_proof"] = False
    report["retained_arm_sweep_evidence"] = str(r5.RUN / "reports/id4_sweep.json")
    report["limitations"] = [
        "whole arm mass and material unknown",
        "nominal fastener envelopes",
        "no physical fatigue/creep/pullout tests",
        "free cable omitted except stub",
        "surface-only bounding-box overlap is unresolved, never declared clear by zero volume",
    ]
    ex = json.loads((OUT / "reports/export.json").read_text())
    l0 = ex["baseline"]["height_above_motor_top_mm"]
    l1 = ex["candidate"]["height_above_motor_top_mm"]
    report["beam_sensitivity"] = {
        "model": "illustrative equal-section cantilever only; height is proxy length, not FEA",
        "width_mm": 16,
        "height_mm": 8,
        "load_N": 0.058 * G,
        "rows": [
            {
                "E_MPa": e,
                "R5_stress_deflection": beam(0.058 * G, l0, 16, 8, e),
                "compact_stress_deflection": beam(0.058 * G, l1, 16, 8, e),
            }
            for e in (500, 1000, 3000)
        ],
    }
    search_result = json.loads((OUT / "reports/search.json").read_text())
    side = max(
        (
            r
            for r in search_result["rendered_candidates"]
            if r["kind"] == "lateral_concept"
        ),
        key=lambda r: r["minimum_cube_visible"],
    )
    _, angle, edge = next(c for c in cases() if c[0] == "cube_10_grasp")
    scene = retained_at(arm, angle)
    h = edge / 2
    scene["DIAGNOSTIC_CUBE"] = box(
        *(x for pair in zip(CENTER - h, CENTER + h) for x in pair)
    )
    view = View(scene, (0, 0, 0), (0, 1, 0), (0, 0, 1), 84, SIZE)
    report["rejected_side_example"] = {
        "id": side["id"],
        "own_mount_in_scene": False,
        "images": [],
    }
    for eye_side in ("left", "right"):
        image = OUT / "images" / f"rejected_side_cube10_{eye_side}.png"
        met = view_metrics(view, side["pose"], eye_side, image)
        report["rejected_side_example"]["images"].append(
            {"side": eye_side, "path": str(image.relative_to(OUT)), "metrics": met}
        )
    view.close()
    report["source_sha256"] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    report["candidate_sha256"] = hashlib.sha256(
        (OUT / "CAD/Robot_250g_compact_D405.step").read_bytes()
    ).hexdigest()
    save("validation.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["search", "export", "validate"])
    args = parser.parse_args()
    {"search": search, "export": export, "validate": validate}[args.command]()
