# XL430 Cable Assembly Evidence

Retrieved and visually inspected 2026-09-23. These are supplier reference images,
not our design drawings or evidence of physical assembly.

- [Official XL430 manual](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#idler-horn-assembly)
- [XL/XC430 idler assembly](https://emanual.robotis.com/assets/images/dxl/x/assembly/xl430/xl_xc430_idler_assembly_new.jpg)
  local `xl430_idler_assembly_new.jpg`, SHA256
  `ff6a5a6f42b197fb15de0364da589bc64c44adc3ceb926e0155281f7dfb66b7a`.
- [Cable assembly precaution](https://emanual.robotis.com/assets/images/dxl/x/assembly/common/x-series_cable_assembly.png)
  local `x-series_cable_assembly.png`, SHA256
  `ff7a7da4c02af119b576d87eb44431037e89b32f0ff965728716871e32fe54cc`.

The assembly illustration shows the rear cover removed for wiring, a cable
through the idler hollow shaft, and a cable at a side outlet before replacing
the cover. The warning photograph distinguishes orderly routing from wires
trapped across the header/cover area. It does not specify a bend radius or
approve this project's host link, wire assumptions, or assembly sequence.

This corrects the earlier interpretation of a straight header-axis access
corridor as the normal cable exit. A straight rear corridor is a hypothetical
diagnostic, not an alternative manufacturer-specified assembly instruction.
The supplied rear-cover CAD is `M05_ref06` in the arm manifest (unnamed supplier
leaf `=>[0:1:1:10]`); that identification is a geometry/image interpretation.
Its broad rear wall makes the previously proposed straight-out path invalid.

Do not machine the servo case or remove/omit its cover to make a CAD path pass.
An idler-cap removal is a specific manufacturer assembly configuration, not
permission to omit arbitrary neighbouring hardware from collision checks.
