import sys
from urllib.parse import quote

from onshape_api import *

name = sys.argv[1]
enabled = sys.argv[2] == "on"
features = api(f"/assemblies/d/{DID}/w/{WID}/e/{ASM}/features")["features"]
f = next(f for f in features if f["name"] == name)
next(p for p in f["parameters"] if p["parameterId"] == "limitsEnabled")["value"] = enabled
if len(sys.argv) > 3:
    for suffix, val in zip(["Min", "Max"], sys.argv[3:5]):
        p = next(p for p in f["parameters"] if p["parameterId"] == "limitAxialZ" + suffix)
        p.update(expression=val + " deg", value=float(val), units="degree")
r = api(
    f"/assemblies/d/{DID}/w/{WID}/e/{ASM}/features/featureid/{quote(f['featureId'], safe='')}",
    "POST",
    {"feature": f},
)
print(name, r.get("featureState"))
