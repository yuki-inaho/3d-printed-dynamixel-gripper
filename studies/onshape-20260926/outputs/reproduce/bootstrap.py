"""Read reference bodies and feature specifications for a new independent import."""

from onshape_api import *

parts = api(f"/parts/d/{DID}/w/{WID}/e/{PS}")
assert len(parts) == 262, "Select the integrated source Part Studio with all 262 bodies"
assert all(p["name"].startswith(("ARM_", "PG3_", "CAM5_")) for p in parts)
save("imported-parts.json", parts)
for kind, eid, out in [("partstudios", PS, "ps-specs.json"), ("assemblies", ASM, "asm-specs.json")]:
    spec = api(f"/api/{kind}/d/{DID}/w/{WID}/e/{eid}/featurespecs")
    assert "message" in spec["featureSpecs"][0], (
        "Legacy spec format changed; update modern() converter before writing"
    )
    save(out, spec)
print("Read 262 source bodies and featureSpecs. Ready to build.")
