"""Record the stated minimal-angle/minimal-extension/lowest-height decision."""

import json

from study import OUT, save

data = json.loads((OUT / "reports/physical-comparison.json").read_text())
viable = [r for r in data["candidates"] if r["static_candidate_pass"]]
chosen = min(
    viable,
    key=lambda r: (
        r["pitch"],
        r["extension_mm"],
        r["loads"]["camera_group"]["height_above_motor_top_mm"],
    ),
)
optical = next(
    r
    for r in json.loads((OUT / "reports/optical-shortlist.json").read_text())
    if r["id"] == chosen["id"]
)
selection = (
    optical
    | chosen
    | {
        "status": "selected_for_full_validation",
        "reason": "Among the 33 explicitly screened physical candidates, choose the lowest passing pitch, then shortest extension at that pitch, then lowest complete camera-group height. Increased payload/extra-material torque is retained as a tradeoff, not scored away.",
        "full_mechanical_global_optimum_claimed": False,
    }
)
save("selection.json", selection)
baseline = data["baseline"]
base_h = baseline["camera_group"]["height_above_motor_top_mm"]
base_m = baseline["partial_load_including_finger_pad_delta"]["wrist"]["reference_abs_Mx_Nm"]
rows = [
    "# 候補選定 — 本検証前の設計決定",
    "",
    f"採用検証候補: **{chosen['id']}**。pitch {chosen['pitch']}°、爪延長{chosen['extension_mm']}mm、glass {chosen['pose']['glass']}mm。",
    "",
    "光学5,040候補→356通過→角度/延長/Y/Zの非劣候補33件を実体化→静的検査31件通過。探索部分集合の採用であり、大域的な最良ではない。光学一次判定はマウントなし。本検証でマウントを加えて再評価する。",
    "",
    "|候補|傾斜°|延長mm|全高（ID5上面から）mm|カメラ群g|爪/パッド追加g|比較部分の手首Nm|静的判定|",
    "|---|---:|---:|---:|---:|---:|---:|---|",
    f"|旧75°|75|0|{base_h:.2f}|{baseline['camera_group']['mass_g']:.2f}|0|{base_m:.6f}|基準|",
]
for r in data["candidates"]:
    m = r["loads"]
    rows.append(
        f"|{r['id']}|{r['pitch']}|{r['extension_mm']}|{m['camera_group']['height_above_motor_top_mm']:.2f}|{m['camera_group']['mass_g']:.2f}|{m['added_finger_pad_mass_g']:.2f}|{m['partial_load_including_finger_pad_delta']['wrist']['reference_abs_Mx_Nm']:.6f}|{'PASS' if r['static_candidate_pass'] else 'FAIL'}|"
    )
m = chosen["loads"]
height = m["camera_group"]["height_above_motor_top_mm"]
moment = m["partial_load_including_finger_pad_delta"]["wrist"]["reference_abs_Mx_Nm"]
rows += [
    "",
    f"採用理由: 参考30°に到達する最小延長は比較グリッド内で20mm。その中で高さが最も低い候補を選んだ。高さは{base_h - height:.2f}mm低下。手首の比較部分モーメントは{base_m:.6f}→{moment:.6f}Nm（{(moment / base_m - 1) * 100:+.2f}%）。",
    "",
    "モーメントの比較部分はカメラ群+250g対象+旧爪に対する追加材料/パッド移動差分。変化しないアーム/グリッパ重量は含まない。カメラ群だけの軽量化を、全体負荷改善とは呼ばない。",
    "",
    f"参考レバー16.7→{16.7 + chosen['extension_mm']:.1f}mm。同断面・同荷重の一様梁近似では応力比{m['finger_uniform_beam_stress_ratio']:.2f}、たわみ比{m['finger_uniform_beam_deflection_ratio']:.2f}。実爪は補強リブがあり、この比を実測耐久性と解釈しない。",
    "",
    "最下部のE30/P30/Y170/Z220とE30/P35/Y165/Z220は、カメラと台座/ねじが干渉したため棄却した。詳細な部品ペアと交差体積はphysical-comparison.json。既存のねじ接触/サーフェス不明は記録を保持し、新規クリアランスの証明に使わない。",
    "",
    "材料・造形方向・摩擦・連続モータートルクは未確認。これは検証用CAD候補であり、耐久性保証/製作承認ではない。",
]
(OUT / "SELECTION.md").write_text("\n".join(rows) + "\n")
print(chosen["id"], height, moment, len(viable), sep="\n")
