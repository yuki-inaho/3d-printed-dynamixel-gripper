import json

from joint_definitions import JOINTS
from make_connectors import connector
from onshape_api import *
from setup_assembly import modern

ledger = ROOT / "joint-connectors.json"
ports = json.loads(ledger.read_text()) if ledger.exists() else {}
for j in JOINTS:
    for endpoint in ["a", "b"]:
        name = "mc_" + j["name"] + "_" + endpoint
        if name in ports:
            continue
        r = connector(name, j[endpoint], j["xyz"], j["axis"], j["rot"])
        if r["featureState"]["featureStatus"] != "OK":
            raise RuntimeError(name)
        ports[name] = r["feature"]["featureId"]
        ledger.write_text(json.dumps(ports, indent=2))

assembly = api(
    f"/assemblies/d/{DID}/w/{WID}/e/{ASM}",
    query={
        "includeMateConnectors": "true",
        "includeMateFeatures": "true",
        "includeNonSolids": "true",
    },
)
save("assembly-before-mates.json", assembly)
instances = {i["name"].split(" <")[0]: i["id"] for i in assembly["rootAssembly"]["instances"]}
specs = json.loads((ROOT / "asm-specs.json").read_text())
spec = next(s["message"] for s in specs["featureSpecs"] if s["message"]["featureType"] == "mate")
mateledger = ROOT / "mates.json"
mates = json.loads(mateledger.read_text()) if mateledger.exists() else {}
for j in JOINTS:
    name = j["name"] if j.get("closing") else "dof_" + j["name"]
    if name in mates:
        continue
    params = {
        p["message"]["parameterId"]: modern(p["message"]["defaultValue"])
        for p in spec["parameters"]
    }
    for p in params.values():
        if p.get("btType") == "BTMParameterNullableQuantity-807":
            p.update(isNull=True, expression="")
    params["mateType"]["value"] = j["type"]
    params["primaryAxisAlignment"]["value"] = False
    params["mateConnectorsQuery"]["queries"] = [
        {
            "btType": "BTMPartStudioMateConnectorQuery-1324",
            "featureId": ports["mc_" + j["name"] + "_" + endpoint],
            "path": [instances[j[endpoint]]],
        }
        for endpoint in ["a", "b"]
    ]
    if "limits" in j:
        params["limitsEnabled"]["value"] = True
        field, unit = ("limitZ", "mm") if j["type"] == "SLIDER" else ("limitAxialZ", "deg")
        for suffix, value in zip(["Min", "Max"], j["limits"]):
            params[field + suffix].update(
                isNull=False,
                expression=f"{value:.12g} {unit}",
                value=value,
                units="millimeter" if unit == "mm" else "degree",
            )
        params = {
            k: p
            for k, p in params.items()
            if not k.startswith("limit") or k in ["limitsEnabled", field + "Min", field + "Max"]
        }
    feature = {
        "btType": "BTMMate-64",
        "featureType": "mate",
        "name": name,
        "parameters": list(params.values()),
    }
    r = api(f"/assemblies/d/{DID}/w/{WID}/e/{ASM}/features", "POST", {"feature": feature})
    save("last-mate.json", r)
    print(name, r.get("featureState"), flush=True)
    if r.get("featureState", {}).get("featureStatus") != "OK":
        raise RuntimeError(name)
    mates[name] = r
    mateledger.write_text(json.dumps(mates, indent=2))
save(
    "assembly-mated.json",
    api(
        f"/assemblies/d/{DID}/w/{WID}/e/{ASM}",
        query={
            "includeMateConnectors": "true",
            "includeMateFeatures": "true",
            "includeNonSolids": "true",
        },
    ),
)
