# 低位置D405・爪延長スタディ（途中保存）

2026-09-26、ユーザー指示により作業途中を保存した。俯角30°、爪+20 mm、D405ガラス中心(-0.2,165,235) mmを選定。旧75°候補に比べカメラ高さは12.40 mm低い一方、250 gとカメラ等の部分モーメントは9.45%増える。実物の耐久性・材料・造形・校正は未確認。

- [作業書](outputs/low-profile-250g/WORKDOC.md)：26/36項目。最終URDF、441閉路/11姿勢FK比較、マニュアル、スキル更新は未完了。
- [公開Onshape V2](https://cad.onshape.com/documents/29e8557c76e89bcf64f50566/v/f6162b4adc88af9d07f1194a/e/d5415bf725ba822741b01703)：左右パッドの所属を修正した版。
- [設計選定](outputs/low-profile-250g/SELECTION.md)、[UI検証](outputs/low-profile-250g/NATIVE-VALIDATION.md)、[出力記録](outputs/low-profile-250g/EXPORT.md)。
- [変換器](https://github.com/yuki-inaho/urdf_from_step/tree/codex/pixi-occt8)：commit `1b2cea3`、Pixi + OCCT 8.0.1、13回帰試験PASS。実モデルの最終変換検証は進行中。

`CAD/final-version.step` が修正版V2の入力。`diagnostics/v1-pad-misassigned` は負の証拠として保存した旧失敗例であり、製作用データではない。標準UI URDF ZIPも旧V1の参考出力である。

保存範囲は `outputs/low-profile-250g` と `work/low-profile` のみ。SHA256は `SNAPSHOT-MANIFEST.json`。秘密情報の既知パターンをZIP内も含め検査し、ブラウザプロファイル、認証状態、HTTPキャッシュ、bytecodeは含めない。スクリプトは当時のディレクトリ構造と元リポジトリのuv環境に依存するため、コピーだけで全操作を再実行できる独立パッケージとはしていない。UI更新スクリプトを公開保存版へ無条件に再実行しない。
