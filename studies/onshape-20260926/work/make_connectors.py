import json

from onshape_api import *
from setup_assembly import modern, partmap

specs = json.loads((ROOT / "ps-specs.json").read_text())
spec = next(
    s["message"] for s in specs["featureSpecs"] if s["message"]["featureType"] == "mateConnector"
)


def connector(name, owner, xyz, rotation_axis="Z", rotation_deg=0):
    params = {
        p["message"]["parameterId"]: modern(p["message"]["defaultValue"])
        for p in spec["parameters"]
    }
    params["originQuery"]["queries"] = [
        {
            "btType": "BTMIndividualQuery-138",
            "queryString": 'query = qCreatedBy(makeId("Origin"), EntityType.VERTEX);',
        }
    ]
    params["ownerPart"]["queries"] = [
        {"btType": "BTMIndividualQuery-138", "deterministicIds": [partmap[owner]["partId"]]}
    ]
    params["transform"]["value"] = True
    for a, v in zip("XYZ", xyz):
        params["translation" + a]["expression"] = f"{v} mm"
    params["rotationType"]["value"] = "ABOUT_" + rotation_axis
    params["rotation"]["expression"] = f"{rotation_deg} deg"
    feature = {
        "btType": "BTMFeature-134",
        "featureType": "mateConnector",
        "name": name,
        "namespace": "",
        "parameters": list(params.values()),
    }
    r = api(f"/partstudios/d/{DID}/w/{WID}/e/{PS}/features", "POST", {"feature": feature})
    save("last-connector.json", r)
    print(name, r.get("featureState"), flush=True)
    return r


if __name__ == "__main__":
    r = connector("mc_joint1_base", "base_link", [0, 0, 20])
    save("connector-test.json", r)
