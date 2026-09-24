# 横開きジョー＋カメラマウント — 納品ファイル

**幾何検証付きの試作設計です。実機製作は未承認です。**

最初に [画像付きレビュー](skills/cad-reverse-parametric/outputs/gripper_camera_lateral/unaccepted/20260922-r1/review_ja.html) をブラウザーで開いてください。外部通信なしで表示でき、閉じ／25°／50°のカメラ視点を切り替えられます。

- [設計と組立案](skills/cad-reverse-parametric/studies/gripper_camera_lateral/README_ja.md)
- [検証結果](docs/gripper_camera_lateral_20260922.md)
- [作業記録](diary/2026-09-22_gripper-camera-lateral.md)
- [手首近傍STEP・50°開き](skills/cad-reverse-parametric/outputs/gripper_camera_lateral/unaccepted/20260922-r1/CAD/hand_50deg.step)
- [全腕STEP・50°開き](skills/cad-reverse-parametric/outputs/gripper_camera_lateral/unaccepted/20260922-r1/CAD/full_arm_50deg.step)
- [新規3部品のSTEP/STL](skills/cad-reverse-parametric/outputs/gripper_camera_lateral/unaccepted/20260922-r1/CAD/parts/)

基準は混在サーボ版（XL430×2＋XL330系×4）です。全XL430版の未解決干渉を承認していません。既存ジョーは固定指＋回転指の機構を維持し、形状を作り替えず手首で90°組み替えています。

カメラ型番、実画角、実ねじ長・有効ねじ深さ、強度、実配線、全関節の動作・実機校正が未確認です。特に4 mmフランジ追加によるねじ長の変更を現物で確定してください。カメラ・サーボを含むアセンブリSTEPを一体印刷しないでください。STLは新規3部品だけの検討用で、造形方向・材料・スライス条件は未承認です。

GitHubへのpush／PR作成は行っていません。変更対象は元ZIPに対する `delivery_manifest.json` を参照してください。元の `hardware/` の全ファイルはバイト単位で保存しています。
