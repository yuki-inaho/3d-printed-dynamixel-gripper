# 参考機構と入力根拠

2026-09-26、Codex。入力ファイルの絶対パス、SHA256、実測面/体積は `reports/input-intake.json`。

Robonineの[Camera Compatibility](https://github.com/roboninecom/SO-ARM100-101-Parallel-Gripper)にはRealSense D405が明記され、[モデル一覧](https://github.com/roboninecom/SO-ARM100-101-Parallel-Gripper/blob/305ad0f6e8f19e4e739616160cbdc7cae1ab153f/models/README.md)には専用 `RB9.01.060.110 D405 holder.STL` がある。今回、この固定commitのSTLを取得して形状を測定した。主要な取付面法線は(±0.866, ±0.5, 0)、基準面法線(±1,0,0)に対して約30°。STL全体の寸法は28.397×106.453×53mmで、水密メッシュである。これはSTL内の基準面との角度であり、別機構の世界座標へそのまま位置を転記できることは意味しない。

前回の75°案は、爪固定・中央pitch40°以上の限定探索の採用案だった。「最良」はその範囲に限るべきだった。D405だからSO101の浅い配置が不可能という説明は不適切。今回はカメラと把持対象の相対位置を変える。

PG3中立姿勢の爪はY197.6..225.6mm、パッドはY204.6..224.6mm。指取付ボルトはY203.2mmまで、パッド中心はY214.6mm。指を根元ごと平行移動すると取付が壊れるため、ボルトより先・パッドより手前の断面を延長し、パッドと先端だけを前へ出す。根元形状は元のCADと比較する。

[D400シリーズデータシート2025年8月](https://realsenseai.com/wp-content/uploads/dlm_uploads/2025/08/Intel-RealSense-D400-Series-Datasheet-August-2025.pdf)に基づく既存固定仕様を継承する。D405は42×42×23mm、58g±10%、深度原点はガラスから3.7mm内側、ステレオ基線18mm、H84°、MinZは848×480で70mm/1280×720で100mm。848×480で5mmの余裕を設け75mm以上を評価。実校正値、レンズ歪み、照明、反射による欠測はCADだけでは検証できない。今回web取得はタイムアウトしたため、以前に保存・確認済みの公式資料と既存D405仕様を利用し、取得失敗を新しい資料確認成功とは記録しない。

250gの把持位置を10mm前に出すと、その物体だけで水平姿勢の重力モーメントは0.0245166Nm増える。カメラ移動による減少、追加プラスチック質量、爪曲げを別々に積算する。モーターのストールトルクを連続許容トルクとして使わない。

再現: `rtk proxy uv run --project . --no-sync python work/low-profile/research.py`。参考STLは `work/low-profile/cache/`。参考CADの再配布前には同commitのライセンスを併置する。解析JSONの数値は推測寸法ではなく今回取得したCADからの値。
