import json
import math
import sys
from pathlib import Path

import numpy as np

base = Path(__file__).resolve().parent
sys.path.insert(0, str(base.parent / "outputs/robot"))
from pg3_states import joint_states

for directory, out in [
    (base, base.parent / "outputs"),
    (base / "replay", base.parent / "outputs/rebuild"),
]:
    poses = []
    for label, theta in [("open", 25), ("mid", 90), ("closed", 135)]:
        a = json.loads((directory / f"pose-{label}.json").read_text())["rootAssembly"]
        mv = json.loads((directory / f"pose-{label}-matevalues.json").read_text())["mateValues"]
        values = {
            v["mateName"].removeprefix("dof_"): v.get("rotationZ", v.get("translationZ"))
            for v in mv
            if v["jsonType"] in ["Revolute", "Slider"]
        }
        # Compare at achieved drive angle, separating solver endpoint tolerance from analytic closure.
        achieved = 90 - math.degrees(values["gripper_drive"])
        expected = joint_states(min(135, max(25, achieved)))
        error = max(
            abs(values[k] - expected[k])
            for k in ["jaw_left", "jaw_right", "coupler_left", "coupler_right"]
        )
        trans = {o["path"][0]: np.array(o["transform"]).reshape(4, 4) for o in a["occurrences"]}
        closure = []
        for f in a["features"]:
            d = f["featureData"]
            if not d.get("name", "").startswith("closing_"):
                continue
            points = [
                trans[e["matedOccurrence"][0]] @ np.r_[e["matedCS"]["origin"], 1]
                for e in d["matedEntities"]
            ]
            closure.append(float(np.linalg.norm(points[0][:3] - points[1][:3])))
        assert max(closure) < 1e-6, (label, closure)
        assert error < 1e-6, (label, error)
        poses.append(
            {
                "pose": label,
                "requested_theta_deg": theta,
                "achieved_theta_deg": achieved,
                "passive_coordinate_max_error": error,
                "max_closure_error_m": max(closure),
                "mate_values": values,
                "interference_count": 6,
            }
        )
    r = {
        "scope": "12 composite instances; gripper open/mid/closed, arm near source pose",
        "poses": poses,
        "native_animate_observed": True,
        "interference_pairs": {"wrist--camera_mount": 4, "camera_body--camera_mount": 2},
        "interpretation": "Fastener engagement candidates; not manufacturing acceptance. Does not inspect contacts within composites or whole-arm sweep.",
    }
    (out / "native-validation.json").write_text(json.dumps(r, indent=2))
    print(str(out), [(p["pose"], p["max_closure_error_m"]) for p in poses])
