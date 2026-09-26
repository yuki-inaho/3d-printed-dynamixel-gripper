# Source and modification notice

Integrated source used on 2026-09-26:
`3d-printed-dynamixel-gripper/outputs/camera-mount-id5-overhead-d405-r5/CAD/ID5_D405_mid_ASSEMBLY.step`
SHA256 `5a60d93b5feef6957bef5a0a732fd26d3b147f1e7e39917eb87cf5d28943dbf1`.

- Local integrated design: https://github.com/yuki-inaho/3d-printed-dynamixel-gripper
- Arm source: https://github.com/yuki-inaho/low_cost_robot ; upstream low cost robot by Alexander Koch, Copyright (c) 2024 Alexander Koch. MIT text retained in `licenses/arm-MIT.txt`.
- PG3 donor: Robonine — SO-ARM100/101 Parallel Gripper, Copyright (c) 2025 Robonine, https://github.com/roboninecom/SO-ARM100-101-Parallel-Gripper . Hardware source uses CERN-OHL-P-2.0; original NOTICE, licensing map and licence texts are retained under `licenses/robonine/`.

Modifications in this task (2026-09-26): imported the integrated STEP into Onshape; grouped bodies into 12 rigid links; defined robot mates, closed-loop constraints and provisional limits; exported STL/URDF with onshape-to-robot 1.8.3; supplied nonlinear PG3 joint-state mapping; made a portable kinematic URDF by correcting asset references and omitting unmeasured zero inertial entries. The camera mount was redesigned and the camera assembly relocated for compact candidate C_y185_z250_p75 (rearward12 mm, downward7 mm, pitch65 to75 deg); wrist export limits became -106 to138 deg. The original integrated source is preserved.

The files are provided as a kinematic study. Source licence notices remain applicable; this notice does not relicense third-party CAD, supplier representations or the integrated source repository.


Exported candidate STEP SHA256: f7cd3b6d61363c328c9a26cd582d2eff2893cbee408143b11e9178c99498c065. Export source: https://cad.onshape.com/documents/7b85d8922959cbe564b6e0cb/v/e21cffef1877c8f91d2b03f8/e/848ae15cd82797bd99cdc330.

License reference supplements: missing relative-link targets from Robonine LICENSING.md were retrieved from commit 305ad0f6e8f19e4e739616160cbdc7cae1ab153f. Its LICENSING.md was byte-identical to the retained source copy. REUSE.toml describes that upstream repository, not a new licence grant over this entire robot. See ../reports/license-link-repair.json for URLs and hashes.
