# 低配置D405 — 引き継ぎ継続・検証器改善版

**取り込み後の最新記録:** [レビューとOCCT 8実行結果](docs/D405_LOW_PROFILE_INTAKE.md)。
以下は受領時の別エージェントの記録。今回の実行結果は
[integration/verification.json](studies/low-profile-20260926/integration/verification.json) を参照。
個人パス除去後のファイル照合には `python scripts/verify_d405_intake.py` を使う。

対象は `bba1f4e0762b35f84ebe8d3cfaaf41180e453831` と同内容のユーザー提供ZIP。
2026-09-26の継続作業で、**誤合格を防ぐ検証器、実STEPの独立再読込、追試手順**を追加した。
元CADの寸法、Onshape、URDF、STLは変更していない。GitHubへのcommit/pushは行っていない。

## 最初に読む文書

- [今回の結果・追試手順](studies/low-profile-20260926/revalidation/README.md)
- [レビューと未実施事項](studies/low-profile-20260926/revalidation/REVIEW.md)
- [今回の作業書](diary/workdoc_Sep26-2026_low_profile_continuation.md) と [次の引き継ぎ](diary/handoff_Sep26-2026_low_profile_continuation.md)
- 元の設計説明は [研究索引](studies/low-profile-20260926/README.md) と [画像付きマニュアル](studies/low-profile-20260926/outputs/low-profile-250g/MANUAL.html)。

## 今回の改善と検証

重複した11姿勢、不正な同次変換、NaN、部品数の欠落などの誤受理を再現してから修正した。
既存4件に48件を追加し、**52試験PASS**。
関節制限・軸・visual/collision・部品所属・メッシュ参照を固定設定と照合し、
`python -O` でも検査を無効化しない。
新規変換先を `--model` で指定でき、過去の結果を暗黙上書きしない。

保存されたJSONだけでなく、11姿勢×262部品をSTEP本体から再読込した。
その姿勢を用いた441状態の閉路検査・11姿勢のFK照合も元の許容値内。
V1の実データは、爪グループ内の部品に5.164 mmの相対移動を検出して拒否した。
これは **運動学検証のみ** であり、製作承認は引き続き `false`。

旧D6/D7は保存証跡と固定remote情報の監査として完了した。
今回の実行環境は Python 3.13.5 / CadQuery 2.8.0 / cadquery-ocp 7.9.3.1.1。
元のPixi / OCCT 8.0.1による変換器の再ビルド・再変換を今回実行したという意味ではない。
材料、締結保持、連続トルク、摩擦、公差、ケーブル、疲労/クリープ、実カメラ校正のUNKNOWNを保持する。
既存8接触/小隙間FAILと720p距離基準FAILも解消していない。

## 提出ファイルの検査

元アーカイブを別ディレクトリに展開した場合、標準Pythonだけで原本のSHA256を検査できる。
このコマンドは原本用で、個人パス除去後の取り込み先には適用しない。

```sh
python studies/low-profile-20260926/revalidation/verify_bundle.py
```

`BUNDLE-MANIFEST.json` は自分自身を除く提出ファイルの一覧。
ハッシュは転送・展開時の整合性確認であり、署名や製作安全性の保証ではない。
元の入力327件のハッシュ一覧は `revalidation/INPUT-SNAPSHOT-MANIFEST.json` として保持。
今回のコード・文書差分は `CHANGES.patch`、変更対象の一覧は研究内の `revalidation/change-inventory.json`。
差分は入力ZIPに対するもので、Git履歴を新しく作成したものではない。
大きな実行証跡JSON/XML、ハッシュmanifestはpatchの対象外だが、tar.zstにはすべて含む。
