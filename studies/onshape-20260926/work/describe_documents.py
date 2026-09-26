from onshape_api import *

desc = """Kinematic study, 2026-09-26. Source: yuki-inaho/3d-printed-dynamixel-gripper D405 R5 integrated STEP (SHA256 5a60d93b5feef6957bef5a0a732fd26d3b147f1e7e39917eb87cf5d28943dbf1). Arm: low_cost_robot, Copyright (c) 2024 Alexander Koch, MIT. PG3 donor: Copyright (c) 2025 Robonine, SO-ARM100/101 Parallel Gripper, CERN-OHL-P-2.0; https://github.com/roboninecom/SO-ARM100-101-Parallel-Gripper . Modifications: imported, grouped into 12 rigid links, assigned mates/limits, exported STL/URDF. No geometry redesign. Motion and interference sampled; not mass/inertia, hardware or manufacturing validation. Public Free noncommercial study."""
for did in [DID, "531556789fcbb8dfdcac2689"]:
    api(f"/documents/{did}", "POST", {"description": desc})
    d = api(f"/documents/{did}")
    assert d["public"]
    print(did, "public", d["public"], "description updated")
