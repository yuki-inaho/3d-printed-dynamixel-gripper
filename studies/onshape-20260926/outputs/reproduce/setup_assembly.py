import json

from onshape_api import *


def modern(x):
    if isinstance(x, list):
        return [modern(v) for v in x]
    if isinstance(x, dict):
        if x == {"type": 0}:
            return None
        if "typeName" in x and "message" in x:
            return {
                "btType": x["typeName"] + "-" + str(x["type"]),
                **{k: modern(v) for k, v in x["message"].items() if k != "nodeId"},
            }
        return {k: modern(v) for k, v in x.items()}
    return x


parts = [
    p
    for p in json.loads((ROOT / "composite-parts.json").read_text())
    if p["bodyType"] == "composite"
]
names = list(json.loads((ROOT / "composites.json").read_text()))
partmap = dict(zip(names, parts))
name_id = "57f3fb8efa3416c06701d60d"


def metadata(eid, name, pid=None):
    path = f"/metadata/d/{DID}/w/{WID}/e/{eid}" + (f"/p/{pid}" if pid else "")
    return api(path, "POST", {"properties": [{"propertyId": name_id, "value": name}]})


if __name__ == "__main__":
    ledger = ROOT / "instances.json"
    instances = json.loads(ledger.read_text()) if ledger.exists() else {}
    for name, p in partmap.items():
        if name in instances:
            continue
        metadata(PS, name, p["partId"])
        r = api(
            f"/assemblies/d/{DID}/w/{WID}/e/{ASM}/instances",
            "POST",
            {
                "documentId": DID,
                "elementId": PS,
                "partId": p["partId"],
                "isAssembly": False,
                "isFixed": name == "base_link",
            },
        )
        instances[name] = r
        ledger.write_text(json.dumps(instances, indent=2))
        print(name, json.dumps(r)[:160], flush=True)
    metadata(PS, "Robot Links - D405 R5")
    metadata(ASM, "Robot Assembly - URDF")
    save(
        "assembly-initial.json",
        api(
            f"/assemblies/d/{DID}/w/{WID}/e/{ASM}",
            query={
                "includeMateConnectors": "true",
                "includeMateFeatures": "true",
                "includeNonSolids": "true",
            },
        ),
    )
