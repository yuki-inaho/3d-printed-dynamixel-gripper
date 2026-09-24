# Repository Instructions

Current scope (2026-09-24): ID5-only PG3 installation and a new camera-mount
candidate above the ID5 motor, looking diagonally down at the grasp zone. The
older P05-side camera is a rejected visual layout retained for history/tests.
Read `docs/PG3_ID5_ONLY_DESIGN.md`, `docs/CAMERA_MOUNT_ID5_CORNER.md`,
`specs/camera_mount_id5_corner.yaml`, and
`temp/workdoc_Sep24-2026_camera_mount_id5_corner.md` first.
`docs/PG3_INSTALLATION_CANDIDATE.md` and the Sep23 workdocs describe earlier
layouts and are not current acceptance evidence.
The user's DoD is actual installability, not import, rendering or diagnostics.
Earlier candidates remain: rack/pinion concept and PG2 R5 upright crank-slider.
Read `docs/REVIEW_PG2_AND_SELF_AUDIT.md` for corrected acceptance status.
2026-09-24: roll is no longer required; the earlier ID5 roll reservation is superseded.
ID5 drives the jaw, with no additional motor (user confirmed).
Physical-to-CAD observation is still pending. Frozen r5 retains the old layout.
P05 local cable-relief candidate design is authorized; preserve original STEP,
holes, fastening/contact faces and support function. No printing/energizing approval.

Read `docs/HANDOFF.md`, then `docs/REQUIREMENTS.md` before changing CAD.
The deliverable includes the ID4-to-ID5 link, the ID5 XL430 jaw mechanism,
and a candidate fixed to the ID5 motor case, subject to fastener-function and
case-clamping validation. PG2 standalone intake is not whole-arm fit.
Current workdoc: temp/workdoc_Sep24-2026_pg3_id5_only.md.
Current design specification: docs/PG3_ID5_ONLY_DESIGN.md.

- Use `uv`; local shell commands use `rtk proxy ...`. Never access serial ports,
  command motors, change IDs, or energize hardware as part of CAD validation.
- Requirements and gate definitions outrank attractive renders and green unit tests.
  Unknown, failed, errored and not-applicable are distinct states.
- Read `skills/cad-reverse-parametric/SKILL.md` for CAD design/validation.
  The `references/` tree contains donor CAD and historical review material;
  treat it as evidence, not approved design.
- Workdoc creation/review: use the separate `write-workdoc-uv`,
  `review-written-workdoc`, `start-work-with-docs` skills under `skills/`.
- Browser automation uses the independent `skills/playwright-cli/SKILL.md`.
  Use a dedicated **headless** named session. Do not close another session,
  edit a shared Chili3D public directory, or assume measure selection is tree selection.
- `references/` is immutable evidence. Create candidates under a unique
  `outputs/<run-id>/`; never overwrite the donor or promote an unaccepted checkpoint.
- Physical IDs, URDF joint names and CAD J-labels are different namespaces.
  Six CAD motor occurrences do not prove six physical IDs. Resolve mapping first.
- Existing link edits preserve geometry outside an approved local change mask.
  New gripper design is authorized, but unrelated whole-arm redesign is not.
- No implicit healing, skipped collision partners, enlarged tolerances or smaller
  coverage to turn a failed test green. Change requirements only by recorded decision.
- Copying inherited generic tools is not validation of their thresholds. Pin versions,
  use independent positive/negative controls and test real exported artifacts.
- Keep design specification, executable plan, evidence and decision log separate.
  Apply manual edits with apply_patch; preserve unrelated user changes.

Skill copies are project-local, not globally installed. Their portable entrypoints
are `skills/*/SKILL.md`; `.codex/skills` discovers the CAD and Playwright copies.
