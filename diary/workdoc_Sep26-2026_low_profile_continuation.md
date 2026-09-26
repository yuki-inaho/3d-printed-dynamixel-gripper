# 作業計画書 兼 記録書 — 低配置D405の監査・検証器改善

日付: 2026-09-26 / 作業者: ChatGPT / 開始: 20:27:35 JST+0900

## 1. 作業目的

指定コミット `bba1f4e0762b35f84ebe8d3cfaaf41180e453831` の引き継ぎを継続し、
D6/D7の証跡監査と、保存済み実モデルを別環境で正しく検査できる改善を行う。
最終提出はユーザー指定の zstd（tar.zst）とする。

### 1.1 ゴール要求分析

ユーザーの目的は引き継ぎ後の改善継続であり、既存の合格表示を増やすことではない。
今回確認した「11姿勢の重複を受理」「不正な同次変換を受理」「再変換先を直接指定できない」
という検証器の不備を修正する。CAD設計寸法・材料・物理的許容値は変更しない。
既存の閉路1e-6 m、姿勢2e-5 m/radの基準を維持する。
データ構造検査を追加するが、機械性能の新しい受入閾値は作らない。

非ゴール: Onshape編集、追加設計候補、全アーム再設計、印刷、通電、実機試験、
物理的FAIL/UNKNOWNの解消を装うこと。過去のOCCT 8実行と今回の別環境検証を混同しない。

### 1.2 作業場所・入力・制約

作業場所: `.`。
入力ZIPのcommentは上記コミットと一致し、元の研究snapshot 327ファイルはSHA256全件一致。
GitHub connectorでも同ブランチの先頭コミットを確認した。
ZIPはGit履歴を含まないため、ローカルGit indexを入力との差分検査専用に用いる。
そのindexをupstream履歴と主張しない。今回の成果はアーカイブ提出でありremoteは変更しない。

元PCのrtk、Pixi、pythonocc-coreはこの実行環境にない。シェルの外部DNSも利用不可。
`uv run --no-project --offline --python python` で既存環境を明示使用する。
NumPy 2.3.5 / SciPy 1.17.0 / trimesh 4.11.1 / pytest 9.0.2。
STEPの独立再読込はインストール済みCadQuery 2.8.0 / cadquery-ocp 7.9.3.1.1を用いる。
これは元のCadQuery 2.7環境または変換器のOCCT 8.0.1の再現ではない。

### 1.3 トレーサビリティ

|ID|目的|成果物・検証|
|---|---|---|
|C1|旧D6/D7の事実確認|revalidation/handoff-audit.json、旧作業書への監査追記|
|C2|誤合格を防ぐ|robot/validate_robot.py、追加負対照、RED/GREEN XML|
|C3|実データで独立再検証|robot/replay_step.py、全11姿勢STEP、441閉路、別出力先|
|C4|次の作業者が追試可能|README、依存記録、差分、SHA256、tar.zst展開検査|

## 2. 作業内容

調査で既存証跡と実行環境を分離する。変更前に不良対照を実行し、
検証器を明示例外・入力集合検査・有限値/剛体変換検査・由来ハッシュ検査へ修正する。
モデルを引数で指定し、過去のvalidation.jsonを暗黙上書きしない。
STEP再読込では全構成部品の所属と変換を検査し、V1パッド誤所属も拒否する。
不良データは検査失敗を非ゼロ終了として報告し、黙って省略しない。

## 3. 作業チェックリスト

### 手順1: 証跡監査（C1）
- [x] 🖐 **操作**: 指定コミット・ZIP・327件snapshotを照合する。
- [x] 🔎 **確認**: D6のUIログ・API集計・公開仕様を照合し、過去counterと現在の呼出しを分ける。
- [x] 🧪 **テスト**: D7の固定commit・lock・公式release・実行ログ・XML・成果物を照合する。
- [x] 🛠 **エラー時対処**: 本環境で再実行できない経路と、監査判定の範囲を明記する。

### 手順2: 検証器の堅牢化（C2）
- [x] 🖐 **操作**: 変更前の誤合格を負対照テストで保存する（RED）。
- [x] 🔎 **確認**: 入力契約・姿勢集合・所属・行列・関節・collision・出力先を明示した修正を実装する。
- [x] 🧪 **テスト**: 既存4件と追加負対照を実行する（GREEN、python -Oも対象）。
- [x] 🛠 **エラー時対処**: テストで判明した不備を直し、失敗ログと基準不変を記録する。

### 手順3: 実STEPによる独立検査（C3）
- [x] 🖐 **操作**: 保存済みSTEP再読込を引数指定・別出力先で実装する。
- [x] 🔎 **確認**: 262部品の11姿勢を読み直し、全member・所属・入力SHAを確認する。
- [x] 🧪 **テスト**: 再生成した姿勢情報で441閉路と11姿勢を検証し、V1不良対照も拒否する。
- [x] 🛠 **エラー時対処**: OCCT8変換の再実行と独立検査の違いを明記し、未知を保持する。

### 手順4: 記録・提出（C4）
- [x] 🖐 **操作**: 追試README・レビュー・引き継ぎと作業記録を同期する。
- [x] 🔎 **確認**: 改変ファイル一覧・入力保持・diff check・全テストを最終確認する。
- [x] 🧪 **テスト**: tar.zstを作成し、zstd検査・展開後SHA256を全件照合する。
- [x] 🛠 **エラー時対処**: 未実施事項と残存リスクをREADMEと最終報告へ残す。

## 4. コマンド

再現コマンドは `studies/low-profile-20260926/revalidation/README.md` に完成後の実行例を保存する。
元のwork/配置を模した秘密プロファイルや認証キャッシュは作らない。
手編集はapply_patch。各項目は完了確認後に一つずつチェックし、直後に本書へ記録する。

## 5. 注意事項

保存済みCAD、STL、references、V1負の証拠を変更しない。
失敗した判定、未検証、対象外を区別する。過去の成功ログを今回実行したログとしない。
作業書への完了記録は後回しにしない。停止した項目は未チェックとし原因と再開条件を残す。
GitHub commit/push、Onshape更新、材料・造形方向の決定は今回実施しない。

## 6. 完了の定義

- [x] C-D1: 誤合格の再現・修正・再試験が追跡でき、実データの許容値を変えていない。
- [x] C-D2: 実STEP再読込と保存URDFの再検証結果があり、実行環境と範囲が明示される。
- [x] C-D3: 提出アーカイブを実展開し全ファイルを検査し、未実施を明示する。

## 7. 作業記録

|日時 JST|対象|実施内容・結果・証跡|
|---|---|---|
|2026-09-26 20:27:35|開始|dateで時刻確認。指定handoff/WORKDOC/AGENTSとスキルを読んだ。|
|2026-09-26 20:30:51|環境|uvのoffline明示実行でpythonを確認。元rtk/Pixi不在を記録。|
|2026-09-26 20:33:13 JST+0900|🖐 **操作**: 指定コミット・ZIP・327件snapshotを照合する。|input-integrity.json: ZIP comment bba1f4e...、研究327件SHA一致。GitHub現branch先頭も一致。|
|2026-09-26 20:33:14 JST+0900|D6開始|API-USAGE、35 UIログ、headless/最終V2画像と公開API制限を照合。元counter実体はZIP外のためlive値を確認したとはしない。|
|2026-09-26 20:33:15 JST+0900|🔎 **確認**: D6のUIログ・API集計・公開仕様を照合し、過去counterと現在の呼出しを分ける。|handoff-audit.json D6 PASS_ARCHIVED_EVIDENCE。35 UIログと最終描画画像を照合。source scan 0。counter526は過去記録、今回Onshape操作/APIとも0。|
|2026-09-26 20:33:55 JST+0900|🧪 **テスト**: D7の固定commit・lock・公式release・実行ログ・XML・成果物を照合する。|D7 PASS_ARCHIVED_EVIDENCE。固定remote lock/commit・公式V8.0.1・保存runtime/wheel・13+4+18 XML・V2 SHA/12mesh/441/11を実照合。旧作業書D6/D7を一つずつ完了記録。|
|2026-09-26 20:33:56 JST+0900|🛠 **エラー時対処**: 本環境で再実行できない経路と、監査判定の範囲を明記する。|元R5 STEPはZIPに不在。元CAD18環境とPixi/OCCT8再変換は未実施、wheel実体はZIP外。別版のCadQueryによる独立再読込を明示し、過去検証と今回検証を分離。|
|2026-09-26 20:34:50 JST+0900|🖐 **操作**: 変更前の誤合格を負対照テストで保存する（RED）。|hardening-red.xml/log: 12負対照中9 FAIL/3 PASS、pytest exit1で誤受理を実証。最初の--import-mode=importlibは隣接moduleを解決できず収集error、別ログ保持し通常importでやり直した。|
|2026-09-26 20:37:43 JST+0900|RED件数訂正|直前記録の9 FAIL/3 PASSは記載誤り。実XMLとpytest出力は12件中11 FAIL/1 PASS。NaN並進もmax集計で見逃された。|
|2026-09-26 20:43:00 JST+0900|🔎 **確認**: 入力契約・姿勢集合・所属・行列・関節・collision・出力先を明示した修正を実装する。|validate_robot.pyを明示例外・重複/欠落・有限値・SE(3)・固定config/関節/所属・visual/collision・path/hash検査へ修正。--model/--inputs/--nativeと排他的--outputを追加。初回16試験PASS、441/11許容値不変。追加契約テストを実装。|
|2026-09-26 20:44:32 JST+0900|🧪 **テスト**: 既存4件と追加負対照を実行する（GREEN、python -Oも対象）。|contract-tests.xml/log: 既存4+追加40=44 PASS (10.64s)。python -O、固定関節、collision、重複index、外部path、JSON、別モデルCLI/上書き拒否を確認。|
|2026-09-26 20:44:32 JST+0900|🛠 **エラー時対処**: テストで判明した不備を直し、失敗ログと基準不変を記録する。|RED11失敗からGREEN。最初のpatchが重複pathで適用されなかった実行はpatch-not-applied-tests.*として保持。正しい置換後のhardening-green/contract-testsが成功証跡。閉路1e-6m/姿勢2e-5m/radは不変。|
|2026-09-26 20:44:33 JST+0900|🖐 **操作**: 保存済みSTEP再読込を引数指定・別出力先で実装する。|replay_step.pyを追加。全occurrenceをXCAF再読込し、名前/型/数/局所bounds/所属/全member剛体運動/角度/軸pivotを照合。出力新規dir強制、失敗部分もFAILとして保存。|
|2026-09-26 20:45:36 JST+0900|STEP長時間コマンド中断|最初の同期tool実行が時間制限で5姿勢後に中断。成功とは扱わずstep-replay-interrupted/とlogを保持。新規出力dirで全件を再実行中。|
|2026-09-26 20:47:14 JST+0900|🔎 **確認**: 262部品の11姿勢を読み直し、全member・所属・入力SHAを確認する。|step-replay/native-pose-transforms.json: 11×262=2882部品姿勢を実STEPから再抽出。baseline込み3144件。各姿勢207solid/55sheet、全member剛体、局所bounds差0mm。CadQuery2.8/OCP7.9.3.1.1を使用。|
|2026-09-26 20:49:43 JST+0900|🧪 **テスト**: 再生成した姿勢情報で441閉路と11姿勢を検証し、V1不良対照も拒否する。|kinematics-step-replayed.json: closure3.46945e-17m、FK8.78488e-9m/5.33710e-8radで元基準PASS。V1実STEPはsmall_gripper_drive/jaw_lのmember相対移動5.16416212733822mmを検出してFAIL。full-tests.xmlは52 PASS。|
|2026-09-26 20:49:43 JST+0900|🛠 **エラー時対処**: OCCT8変換の再実行と独立検査の違いを明記し、未知を保持する。|START_HERE_ja.md/revalidation READMEへ元OCCT8の証跡監査と本OCP7.9独立実行を分離記載。形状/閾値/製作false、旧物理FAILとUNKNOWNを維持。|
|2026-09-26 20:51:29 JST+0900|🖐 **操作**: 追試README・レビュー・引き継ぎと作業記録を同期する。|START_HERE、README/REVIEW、旧/新handoff、CONVERTER、robot README、依存記録、整合性検査器を追加/同期。52件の範囲、過去監査と新実行、物理未承認を明示。|
|2026-09-26 20:54:13 JST+0900|handoff同期確認|HANDOFF二部は元から相対リンクだけが異なる。byte同一を要求した確認は失敗したが、元の相対prefixを正規化して本文一致を確認。リンクは各配置に合わせて保持、旧WORKDOC二部はbyte一致。|
|2026-09-26 20:54:13 JST+0900|🔎 **確認**: 改変ファイル一覧・入力保持・diff check・全テストを最終確認する。|preservation-check.json: 元1526件中、形状/画像/PDF/skillsの523件は全てbyte一致、欠落0、font0。52試験PASS、compileallとgit diff --check PASS。manifestと差分は提出前に再生成する。|
|2026-09-26 20:58:00 JST+0900|🧪 **テスト**: tar.zstを作成し、zstd検査・展開後SHA256を全件照合する。|packaging-rehearsal.json: 98,848,189 bytesのtar.zst作成、zstd -tと展開exit0。manifest1592件全一致。移設先52試験PASS、STEP11×262再読込と441/11 PASS、姿勢JSONのSHAも同一。改変/未登録ファイルは各exit1で検出。|
|2026-09-26 20:58:01 JST+0900|🛠 **エラー時対処**: 未実施事項と残存リスクをREADMEと最終報告へ残す。|README/REVIEW/handoff/START_HEREにOCCT8新規実行なし、root全suite未実施、元R5 STEP/wheel不在、新規依存install未試験、製作falseと旧FAIL/UNKNOWN、remote/Onshape未変更を記載。|
|2026-09-26 20:58:02 JST+0900|C-D1: 誤合格の再現・修正・再試験が追跡でき、実データの許容値を変えていない。|RED12中11誤受理を保存。GREEN52、最適化Python、別モデルCLI、全member負対照を実試験。元の物理/運動学許容値を変更していない。|
|2026-09-26 20:58:02 JST+0900|C-D2: 実STEP再読込と保存URDFの再検証結果があり、実行環境と範囲が明示される。|V2の全STEPを本配置/実展開先の2か所で再読込し、同一姿勢JSONと441/11一致を確認。環境はCadQuery2.8/OCP7.9であり過去OCCT8とは別。V1実データも幾何的に拒否した。|
|2026-09-26 20:58:03 JST+0900|C-D3: 提出アーカイブを実展開し全ファイルを検査し、未実施を明示する。|提出候補tar.zstを実展開して全件照合し、移設試験・改変負対照・未実施事項の記載を完了。今回の完了記録を封入して最終archiveを作り直し、最後の全件検査はarchive外のSHA/verification記録へ保存する（自己参照を避ける）。|
|2026-09-26 20:59:07 JST+0900|最終記録整形|作業記録表で連結されていた2行を分離し、diaryと同期。内容と時刻は変更せず、提出候補を再封入する。|
