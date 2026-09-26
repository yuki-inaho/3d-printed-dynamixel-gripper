# Source and modification notice

Integrated source used on 2026-09-26:
`3d-printed-dynamixel-gripper/outputs/camera-mount-id5-overhead-d405-r5/CAD/ID5_D405_mid_ASSEMBLY.step`
SHA256 `5a60d93b5feef6957bef5a0a732fd26d3b147f1e7e39917eb87cf5d28943dbf1`.

- Local integrated design: https://github.com/yuki-inaho/3d-printed-dynamixel-gripper
- Arm source: https://github.com/yuki-inaho/low_cost_robot ; upstream low cost robot by Alexander Koch, Copyright (c) 2024 Alexander Koch. MIT text retained in `licenses/arm-MIT.txt`.
- PG3 donor: Robonine — SO-ARM100/101 Parallel Gripper, Copyright (c) 2025 Robonine, https://github.com/roboninecom/SO-ARM100-101-Parallel-Gripper . Hardware source uses CERN-OHL-P-2.0; original NOTICE, licensing map and licence texts are retained under `licenses/robonine/`.

Modifications in this task (2026-09-26): imported the integrated STEP into Onshape; grouped bodies into 12 rigid links; defined robot mates, closed-loop constraints and provisional limits; exported STL/URDF with onshape-to-robot 1.8.3; supplied nonlinear PG3 joint-state mapping; made a portable kinematic URDF by correcting asset references and omitting unmeasured zero inertial entries. No original CAD geometry was redesigned during this task.

The files are provided as a kinematic study. Source licence notices remain applicable; this notice does not relicense third-party CAD, supplier representations or the integrated source repository.
