# 次の引き継ぎ — 検証器改善・独立STEP再検証

2026-09-26。今回の基点は `bba1f4e0762b35f84ebe8d3cfaaf41180e453831` と同じ入力ZIP。
提出はtar.zst。remote commit/pushとOnshape変更は行っていない。

まず [提出物の入口](../START_HERE_ja.md)、
[継続作業書](workdoc_Sep26-2026_low_profile_continuation.md)、
[追試README](../studies/low-profile-20260926/revalidation/README.md)、
[レビュー](../studies/low-profile-20260926/revalidation/REVIEW.md) を読む。

## 完了したこと

旧D6/D7は保存証跡の監査として一項目ずつ照合・記録した。原本作業書と成果物WORKDOCを同期した。
旧検証器の12負対照中11件の誤受理を修正し、既存4＋追加48＝52テストを実行。
validate_robot.pyは--model/--native/--inputsを受け付け、新規--output以外へ書き込まない。
代表部品だけでなく全memberを検査するreplay_step.pyを追加。
V2の11×262部品姿勢を再読込し、441閉路・11FKを元の基準で合格確認した。
V1はsmall_gripper_drive/jaw_lのmember相対移動5.16416212733822 mmを検出し失敗した。

## 次の実行者が注意すること

最終形状は引き続きV2 `f6162b4adc88af9d07f1194a`。CAD/STL/URDFは今回未変更。
元のPG3非線形閉路はpg3_states.pyで解く。線形mimicへ置き換えない。
新しく変換したモデルは必ず--modelで明示指定する。既存--outputへの上書きは意図的に拒否する。
replay_step.pyを移設するときはrepoのscripts/assembly_io.pyとAGENTS.mdも同じ構造に保つ。
認証情報や元PCのbrowser profileは不要で、この提出にも含めていない。

元のPixi/OCCT8変換環境は今回再現していない。過去のbuild/XMLと独立CadQuery/OCP再検証を混同しない。
本環境はPython3.13.5、NumPy2.3.5、SciPy1.17.0、trimesh4.11.1、pytest9.0.2、
CadQuery2.8.0、cadquery-ocp7.9.3.1.1。requirementsは直接依存記録で完全lockではない。
元R5 STEPとconverter wheel実体は入力ZIP外。元CAD18試験の今回再実行は未実施。

製作承認false、物理的FAIL/UNKNOWNは維持する。
材料・造形方向・荷重条件を定める新作業書と実測を、次の設計改善の前提にする。
今回の作業書を根拠なく機構全体の完成・印刷許可へ読み替えない。