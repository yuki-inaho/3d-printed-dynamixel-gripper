# 再現スクリプト

今回のD405 R5 STEPに固有の部品分類と座標を使う。別ロボットへ流用するときは分類・軸・原点・制限を再測定する。

1. Onshapeで新しいpublic Documentを作成し、`source-manifest.json` のSTEPをアップロードする。入力と版を記録。
2. STEP translationがDONEになってから、262ボディを含む統合Part Studioと空のAssemblyのIDを取得する。取り込みが複数タブを生成しても、同名の小部品Part Studioを選ばない。
3. この実行専用のstateフォルダを作り、`project.example.json`を`project.json`として配置し4IDを入力する。stateを別ドキュメントに使い回さない。
4. 以下の環境変数を設定する。鍵は画面や履歴へ直接貼らず、利用環境の秘密値管理方法で読み込む。

```text
ONSHAPE_TASK_WORK    専用stateフォルダの絶対パス
ONSHAPE_TASK_OUTPUT  この再実行の出力先の絶対パス
ONSHAPE_ACCESS_KEY   公式APIキーのaccess key
ONSHAPE_SECRET_KEY   公式APIキーのsecret key
```

```bash
python3 bootstrap.py
python3 build_composites.py
python3 setup_assembly.py
python3 build_joints.py
python3 set_pose.py 25 open
python3 set_pose.py 135 closed
python3 set_pose.py 90 mid
```

各段階は成功分をJSON ledgerへ保存する。途中の通信失敗ではOnshape側の作成状態とledgerを照合してから再実行する。stateにはAPIカウンタを置く。これはexporterや他ツールの呼出しを含まないため、公式Developer画面の利用量も確認する。

ネイティブ検証は `../VALIDATION_GUIDE.md` に従う。成功後にVersionを保存し、`../robot/config.json` を新規出力フォルダへコピーしてurlをそのVersionへ変更する。環境変数は同じ状態で、別途インストールした `onshape-to-robot==1.8.3` を実行する。

```bash
onshape-to-robot /absolute/path/to/new_robot_output
```

エクスポータの未加工URDFは既定の `package://assets/...` とゼロ慣性を含む。今回の利用版への変換内容は成果物READMEに記載している。元の未加工出力も残す。今回の `pg3_states.py` と `validate_robot.py` を使う場合は、関節名・フレーム・軸が同一であることを先に確認する。

このスクリプト群の主要処理は2回の実モデル作成で使用済み。配布版の差分はID設定・秘密値を環境変数へ切り出したことと、stateを別projectへ誤用しないための照合処理。スクリプトだけでネイティブ干渉検出を代替するものではない。

## 利用版への整形

新規出力フォルダに対し `python3 make_portable.py /absolute/path/to/new_robot_output` を実行する。今回のno_dynamics、16リンク／15関節の構成専用。初回の未加工URDFを保持し、相対メッシュ参照・不要要素の除去を適用する。再エクスポートには別フォルダを使う。スクリーンショット付きの全手順は `../manual/MANUAL.html` または `../manual/MANUAL.pdf` を参照。
