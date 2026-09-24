# 再生成と検査

検査環境はPython 3.13、依存版はrequirements.txtの通りです。別のOSや版では幾何判定が変わる可能性があります。寸法単位はmmです。

主形状はdesign.py、カメラはcamera.py、隙間選択品・試験片はcalibration.pyです。design.pyのParametersはこの試作の凍結仕様です。parameters_frozen.jsonは記録用の写しで、自動入力ファイルではありません。モーター取付やガイドのすべての寸法を任意に変更できる汎用設計器と呼ぶものではありません。

依存パッケージを入れた環境で、PG2_XL430フォルダから以下を実行します。

```
python source/check_frame_roundtrip.py
python source/build_release.py
python source/engineering_checks.py
python source/check_saved.py
python source/validate_worker.py 0 30 57
python source/validate_worker.py 1 58 85
python source/validate_worker.py 2 86 113
python source/validate_worker.py 3 114 140
python source/check_camera_delta.py
python source/make_previews.py
python source/release_gate.py
python source/make_report.py
python source/release_gate.py --seal
python source/release_gate.py --verify-manifest
```

validate_worker.pyを並列実行する場合はRAMを確認してください。4並列での実行を使用しましたが、メモリ不足の場合は上のように順番に実行できます。VTKの画像生成は画面なしで行います。

最終版は本体R5＋カメラC3です。最終111姿勢試験はこの組合せを対象にしています。途中のR4/C1/C2の結果はreports/iterationsへ分け、現行版の試験に読み替えません。

guardrails.pyは型番、実際のケース姿勢、実際の出力軸、短い爪、左右対称、金属軸禁止、ケースねじ深さ、非接続印刷品などを検査します。意図的に違反させた12例が拒否されることも検査します。結果が不合格なら、期待値や許容干渉リストだけを変更して通さず、形状・仕様へ戻って修正します。

出力STLは面の向きや破損を自動修復しません。STL形式が持つ重複頂点を座標で統合してトポロジーを検査するだけです。保存STEPは再読込み後の形状だけでなく、組立内の部品間も検査します。前段の検査を通過しても、こちらで不一致が出たら公開を止めます。

参考モーターはreference/内の添付由来データを読みます。extract_reference.pyとprobe_servo.pyは入力抽出の記録で、元アーカイブの場所を前提にしています。通常の再生成には実行不要です。サーボのダミー形状は表示用に出力部と本体へ分けています。内部部品の設計・性能検証はしません。

reports/iterations/には失敗・中断・旧形状が残ります。これらを最終版として印刷しません。製作用の唯一の出力場所はSTL/、最終の組立形状はCAD/です。preview画像・GIFは実CAD由来で、実験動画ではありません。
