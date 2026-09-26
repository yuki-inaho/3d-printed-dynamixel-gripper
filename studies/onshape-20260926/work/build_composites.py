import json
from collections import defaultdict

from onshape_api import *

parts = json.loads((ROOT / "imported-parts.json").read_text())
groups = defaultdict(list)
for p in parts:
    n = p["name"]
    if n.startswith(("ARM_M", "ARM_P")):
        i = int(n[5:7])
        g = ["base_link", "shoulder_yaw", "upper_arm", "forearm", "wrist"][i - 1]
    elif n.startswith("CAM5_"):
        g = (
            "camera_body"
            if n in ("CAM5_D405_BODY", "CAM5_D405_USB_PLUG", "CAM5_D405_USB_CABLE_STUB")
            else "camera_mount"
        )
    elif n.startswith("PG3_"):
        q = n[4:]
        if q in ("link_L", "link_R"):
            g = "coupler_" + q[-1].lower()
        elif q in ("crank", "horn_spacer", "XL430_horn") or q.startswith(
            ("horn_bolt_", "pivot_drive_")
        ):
            g = "gripper_crank"
        elif q.startswith(("carriage_", "finger_", "pad_", "pivot_carriage_")):
            side = "L" if ("_L" in q) else "R"
            g = "jaw_" + side.lower()
        else:
            g = "wrist"
    else:
        raise ValueError(n)
    groups[g].append(p)

order = [
    "base_link",
    "shoulder_yaw",
    "upper_arm",
    "forearm",
    "wrist",
    "gripper_crank",
    "jaw_l",
    "jaw_r",
    "coupler_l",
    "coupler_r",
    "camera_mount",
    "camera_body",
]
manifest = {
    g: [
        {"source_name": p["name"], "part_id": p["partId"], "body_type": p["bodyType"]}
        for p in groups[g]
    ]
    for g in order
}
(OUTPUT / "link-membership.json").write_text(json.dumps(manifest, indent=2))
ledger = ROOT / "composites.json"
made = json.loads(ledger.read_text()) if ledger.exists() else {}
for g in order:
    if g in made:
        continue
    feature = {
        "btType": "BTMFeature-134",
        "featureType": "compositePart",
        "name": g,
        "namespace": "",
        "parameters": [
            {
                "btType": "BTMParameterQueryList-148",
                "parameterId": "bodies",
                "queries": [
                    {
                        "btType": "BTMIndividualQuery-138",
                        "deterministicIds": [p["partId"] for p in groups[g]],
                    }
                ],
            },
            {"btType": "BTMParameterBoolean-144", "parameterId": "closed", "value": True},
        ],
    }
    r = api(f"/partstudios/d/{DID}/w/{WID}/e/{PS}/features", "POST", {"feature": feature})
    if r.get("featureState", {}).get("featureStatus") != "OK":
        save("failed-composite.json", r)
        raise RuntimeError(r.get("featureState"))
    made[g] = r
    ledger.write_text(json.dumps(made, indent=2))
    print(g, "OK", len(groups[g]), flush=True)
save("composite-parts.json", api(f"/parts/d/{DID}/w/{WID}/e/{PS}"))
