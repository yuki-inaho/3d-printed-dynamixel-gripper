# 成果物とGit保存先

- CAD: [public Onshape V2](https://cad.onshape.com/documents/29e8557c76e89bcf64f50566/v/f6162b4adc88af9d07f1194a/e/d5415bf725ba822741b01703)、[固定版STEP](CAD/final-version.step)。
- 人向け: [MANUAL.pdf](MANUAL.pdf) / [HTML](MANUAL.html) / [REPORT](REPORT.md)。
- ロボット: [URDF](robot/model/robot.urdf)、[設定と検証](robot/README.md)。メッシュ12個を含むmodelディレクトリを保ったまま使用する。
- スキル: [4スキルと出典](skills/ONSHAPE-WORKFLOW.md)。リポジトリ直下skills/にも参照ファイルを含め保存。
- 設計保存先: [3d-printed-dynamixel-gripper / codex/onshape-low-profile-d405](https://github.com/yuki-inaho/3d-printed-dynamixel-gripper/tree/codex/onshape-low-profile-d405)、`studies/low-profile-20260926`。
- 変換器保存先: [urdf_from_step / codex/pixi-occt8](https://github.com/yuki-inaho/urdf_from_step/tree/codex/pixi-occt8)、commit `1b2cea3`。

今回の途中保存は設計 `6117edb` と変換器 `1b2cea3`。最終成果物のcommitとremote照合は以下に追記する。commit保存時点と完了後の作業記録を区別し、記録の自己参照SHAは作らない。

35回帰試験、441閉路、11native姿勢、20ページ/19画像、直接Onshape API 0件。動力学、造形強度、実機耐久性・校正は未確認。今回と無関係なlow_cost_robot内のHN11未追跡4ファイルは変更・commitしていない。
