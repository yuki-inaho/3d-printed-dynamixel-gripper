# Onshape標準UI URDF — 修復前V1の比較資料

このZIPは修復前V1 `4577cc931e9bc290e2b31032` のAssembly Exportで取得した比較資料であり、最終ロボットモデルではない。

- V1では左右padが逆側jawへ所属していた。中立配置は正しいが開閉時に反対へ追従するため、後続V2で通常UIから修復する。
- 19 links / 18 joints / 261 visuals、collision 0、inertial 14。`PG3_horn_bolt_1` のvisual参照がない。
- 閉路の全域動作とinertialの実物妥当性は未検証。
- ユーザー指定のSTEP→urdf_from_step/Pixi/OCCTによる最終出力とは区別する。

実操作とスクリーンショットは `../../EXPORT.md`、機械可読の調査は `../../reports/onshape-native-urdf-intake.json`。
