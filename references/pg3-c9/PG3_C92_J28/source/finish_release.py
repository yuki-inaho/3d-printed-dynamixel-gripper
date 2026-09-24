"""Build the human report and require current-revision evidence before packaging."""
from __future__ import annotations
import base64, hashlib, json, zipfile, html, sys
from pathlib import Path
import jaw_revision as j
from jaw_revision import ROOT


def h(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def image(name):
    p=ROOT/'images'/name
    mime='image/gif' if p.suffix=='.gif' else 'image/png'
    return f'data:{mime};base64,'+base64.b64encode(p.read_bytes()).decode('ascii')

def main():
    geometry=h(ROOT/'source/jaw_revision.py'); reports={}
    for name in ['requirements','sanity','motion','assembly','saved','refined_clearance']:
        path=ROOT/'reports'/f'{name}.json'; data=json.loads(path.read_text())
        if data['revision']!=j.REVISION or data.get('source_sha256')!=geometry or not data.get('pass',data.get('pass_',False)):
            raise RuntimeError('Missing, failed or stale report: '+name)
        reports[name]=data
    q=reports['requirements'];m=reports['motion'];s=reports['saved'];a=reports['assembly']
    minimum=min(x['distance_mm'] for x in m['distance_records'] if not x['designated_fit'])
    failed_mutations=[x for x in q['negative_tests'] if not x['rejected']]
    if failed_mutations:raise RuntimeError('Mutation not rejected')
    checks={
        'geometry_requirement_gates':q['jaw_requirements']['pass'],
        'frozen_C7_components_compared':all(x['pass_'] for x in q['frozen_components']),
        'full_assembly_221_pose_collision':m['pass'],
        'changed_part_distances_and_refinement':not m['nonfit_distance_failures'] and reports['refined_clearance']['pass'],
        'revised_stage_assembly_paths':a['pass_'],
        'exported_meshes_and_STEP_reread':s['pass'],
        'grasp_space_and_full_pad_backing':all(x['pass'] for x in q['grasp_space_tests']) and q['jaw_requirements']['checks']['pad_20x28_backed_by_full_5mm'],
        'six_negative_geometry_tests':len(q['negative_tests'])==6 and not failed_mutations,
        'documented_load_review_not_physical_approval':(ROOT/'reports/load_review.json').is_file(),
    }
    release={'revision':j.REVISION,'cad_prototype_pass':all(checks.values()),'checks':checks,
        'source_sha256':geometry,'report_sha256':{n:h(ROOT/'reports'/f'{n}.json') for n in reports},
        'physical_strength_approved':False,'physical_grasp_tests_performed':[],
        'limitations':['Nominal discrete CAD geometry only','Print fit, friction, force, strength, wear, real workpiece retention and release are not qualified',
                       'All motions evaluated with standard C7 cap clearance; camera/arm/cable not evaluated']}
    (ROOT/'reports/RELEASE_CHECK.json').write_text(json.dumps(release,indent=2,ensure_ascii=False))
    if not release['cad_prototype_pass']:raise RuntimeError('Release rejected')
    readme=f'''# C92-J28 — 小型の駆動部に、把持面の広い爪を組み合わせる改訂

版: {j.REVISION} / 作成: 2026-09-23

**CAD上の試作検査を完了。印刷・実組立・摩擦・把持力・強度・摩耗は未検証です。**

## 変更の要点
前案は全奥行62 mmを優先し、爪と接触パッドを短くしすぎました。今回は本体の小型化を維持し、爪の前方への張り出しと連続した把持面を増やしました。

| 寸法 | C7 | C92-J28 |
|---|---:|---:|
| 全幅 | 92 mm | 92 mm |
| 全高 | 63.25 mm | 63.25 mm |
| 爪の前後長 | 12.1 mm | 28 mm |
| 爪の高さ / 板厚 | 36 / 5 mm | 36 / 5 mm |
| パッドの高さ×奥行×厚さ | 28×3×1 mm | 28×20×1 mm |
| 案内シューの移動方向の長さ | 14 mm | 18 mm |
| 最大開口（左右1 mmパッド込み） | 48.895 mm | 48.895 mm |
| 閉位置の開口 | 0.927 mm | 0.927 mm |
| サーボ背面から爪先まで | 61.8 mm | 77.7 mm |

爪は単純に拡大していません。穴位置・座面をそのままに、根元へ補強リブを追加し、把持面の貫通窓をなくしました。パッド全域に5 mm厚の裏打ちがあります。
上下のシューは中央側へ4 mm延長しました。クランクを避けるため、延長部分の内縁には0.5 mmの逃げを設けています。閉じ位置の左右スライダ最短距離は1.927 mmです。

## 変更しないもの
単一XL430-W250の背面直立配置、枠、押さえ、クランク、リンク、ホーンスペーサー、元の締結品と穴位置です。金属の案内棒・別体の金属カラー・直動軸受はありません。通常ねじ・ナット・座金は既存どおり使用します。カメラと全腕接続は対象外です。

## 納品内容
- CAD/C92_J28_open.step、mid.step、closed.step: 名称付き組立CAD。世界Xが開閉、Zが上、-Yが前です。
- STL/changed_parts/: 左右スライダと左右爪の4個。すべて各1個です。
- STL/unchanged_C7/: 基本形状を変更していない残りの部品。新規製作時は全部で9種類11個です。
- CAD/parts/: 部品STEP。これは構築座標であり、印刷姿勢や組立移動位置とは別です。
- REVIEW_ja.html、docs/: 設計・作業・組立・現物受入資料。
- reports/: この版で実行した結果。iterations/C8には距離不足で不合格だった前段の記録。
- source/: 再生成と検査。reference/C7は使った旧版ソースとサーボ模型であり、現物保証ではありません。

## 実行したCAD検査
{len(q['frozen_components'])}件の旧版形状・配置照合、1,101点の運動拘束式、25〜135°を0.5°刻みで221姿勢の全組立干渉、45姿勢の変更部接近距離を確認しました。不許可の交差体積が0.01 mm³を超える組合せは0件です。指定嵌合・同一剛体群の締結を除いた、変更部を含む組合せの最小測定距離は{minimum:.3f} mmです。クランクと延長シューには95〜125°を0.1°刻みで追加検査しました。
工程別挿入9経路・工具軸18件、標準9 STL・3組立STEPの再読込みが合格です。6種類の意図的な誤形状も拒否しました。
10/25/45 mm幅の箱と直径25 mmの円柱が両パッドに接触し、前方の経路で他部品と交差しないことを検査しました。把持面全域の裏打ちも体積で検査しています。これは物体保持の試験ではありません。

## 荷重をどう扱ったか
爪が長いほど同じ力でも案内部へのモーメントが増えます。5 N/爪を仮の計算点とすると、パッド中央で旧約107.5 Nmmから新139.5 Nmmへ増えます。先端寄りでは189.5 Nmmです。
支持長を内側へ延ばして荷重を受ける距離を広げましたが、それで摩擦・強度が保証されるわけではありません。reports/load_review.jsonの反力・摩擦・単純梁の値は、明記した仮定による計算例です。実測の材料特性や摩擦係数を使った有限要素解析ではありません。5 Nは耐荷重でも定格でもありません。
接触面が広いことは、保持力が面積比例で増えるという意味ではありません。設計の目的は、物を差し込む深さと接触位置の選択肢を確保することです。

## 再生成
requirements.txtの環境を用意し、source/rebuild.pyを実行します。旧版のレポートを再利用せずにCAD・検査・画像・レビューを再生成します。実機へ指令を送るコードは含みません。

## 出典と区別
元の機構構成は会話中のMini Max作例を参照しました。今回の28 mm、18 mm、78 mm上限はこの改訂の設計判断であり、元記事の寸法ではありません。
案内の荷重点・支持間隔について参考にしたメーカー説明は igus「The 2:1 Rule and How to Define Fixed and Floating Bearings」です。その製品固有の2:1数値を、この印刷ガイドの合格基準として移植していません。
https://www.igus.com/company/linear-guides-the-2-1-rule-ca
サーボの制御情報: https://docs.robotis.com/docs/dxl/model_reference/x_series/xl_series/xl430-w250/
'''
    (ROOT/'README_ja.md').write_text(readme)
    # Keep source text readable separately; only the HTML embeds pictures.
    rows=''.join(f'<tr><td>{html.escape(k)}</td><td>{"合格" if v else "不合格"}</td></tr>' for k,v in checks.items())
    page=f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>C92-J28 把持部改訂</title>
<style>body{{max-width:1100px;margin:30px auto;padding:35px;color:#20303b;background:#fff;font:16px/1.9 system-ui,sans-serif}}h1{{font-size:32px}}h2{{margin-top:40px;border-bottom:1px solid #ccd6de;padding-bottom:8px}}img{{max-width:100%;height:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #dce3e8}}.note{{padding:16px;background:#fff3db;border-left:4px solid #c8942e}}.sub{{color:#5c6a75;font-size:14px}}pre{{white-space:pre-wrap;font:15px/1.9 system-ui,sans-serif}}@media(max-width:700px){{body{{margin:0;padding:20px}}h1{{font-size:25px}}}}</style></head><body>
<p class="sub">{j.REVISION} / 2026-09-23</p><h1>駆動部は小さく。爪には、つかむための奥行を。</h1>
<p>本体幅92 mmとXL430の直立配置は維持し、爪の前後長を28 mm、パッドの奥行を20 mmにしました。根元の補強と、中央側へ延ばす案内シューも同時に変更しています。</p>
<div class="note"><strong>CAD試作の検査を完了しています。実機の保持力・摩擦・強度・寿命は未検証です。</strong></div>
<img src="{image('comparison.png')}" alt="同縮尺の旧新比較">
<h2>数値と変更範囲</h2><table><tr><th>項目</th><th>C7</th><th>C92-J28</th></tr>
<tr><td>全幅 / 全高</td><td>92 / 63.25 mm</td><td>変更なし</td></tr><tr><td>爪の前後長</td><td>12.1 mm</td><td>28 mm</td></tr>
<tr><td>パッド高さ × 奥行 × 厚さ</td><td>28 × 3 × 1 mm</td><td>28 × 20 × 1 mm</td></tr>
<tr><td>案内シュー長</td><td>14 mm</td><td>18 mm</td></tr><tr><td>最大開口</td><td>48.895 mm</td><td>48.895 mm</td></tr>
<tr><td>全奥行（サーボ背面〜爪先）</td><td>61.8 mm</td><td>77.7 mm</td></tr></table>
<p>交換する印刷品は左右の爪と左右のスライダです。枠・押さえ・駆動部・モーター取付・締結品は変えません。パッド全域の裏には5 mm厚の板を残し、窓やねじを置きません。</p>
<h2>把持空間</h2><img src="{image('grasp_space.png')}" alt="25mm幅のCAD試験物体"><p class="sub">幅25 mmの箱は空間確認用です。10/25/45 mmの箱と直径25 mmの円柱で接触・前方経路を確認しましたが、持ち上げた実績ではありません。</p>
<h2>検証と修正</h2><p>C8では体積干渉0でも、延長シューとクランクの距離が0.177 mmしかありませんでした。C9ではシュー延長部の内縁だけを0.5 mm逃がし、閾値を緩めずに再検査しました。支持長18 mm、全幅、開口は維持しています。</p>
<p>最終版は221姿勢の体積検査、45姿勢の変更部距離、301姿勢の局所距離検査、9挿入経路、18工具軸、9 STL、3組立STEPの再読込みを実行しました。非嵌合の変更部最小測定距離は{minimum:.3f} mmです。連続した全軌道の保証ではありません。</p>
<table><tr><th>CAD完了条件</th><th>結果</th></tr>{rows}</table>
<h2>長くした分の負担</h2><p>仮に片爪5 Nとすると、パッド中央の力による案内まわりのモーメントは107.5 → 139.5 Nmmへ約30%増えます。先端寄りでは189.5 Nmmです。これは位置から求める静力学であり、耐荷重試験ではありません。</p>
<p>支持部の延長は負担の偏りを減らすための設計措置ですが、実際の摩擦係数・がた・変形は未測定です。単純梁計算の小さい変位を、そのままグリッパー全体の強度・精度とみなしていません。保持力が接触面積に比例するともしていません。</p>
<h2>交換部品の印刷</h2><img src="{image('changed_print_atlas.png')}" alt="交換4部品の印刷姿勢"><p>各1個と28×20×1 mmのパッド2枚が必要です。すでにC7を作っている場合、枠と駆動部を再印刷する必要はありません。サポート跡が案内面に残らない配置とし、層表示を確認してください。</p>
<h2>開閉表示</h2><img src="{image('motion.gif')}" alt="実CADの開閉"><p class="sub">実CADの剛体運動です。表示速度は説明用で、サーボの実速度ではありません。</p>
<h2>資料</h2><p>ZIP内のREADME_ja.md、docs/WORK_ORDER_ja.md、docs/ASSEMBLY_AND_ACCEPTANCE_ja.md、reports/RELEASE_CHECK.jsonを参照してください。変更前の失敗はreports/iterations/C8に保存しています。</p>
<h2>参考</h2><p><a href="https://www.igus.com/company/linear-guides-the-2-1-rule-ca">igus: 荷重点と支持間隔</a>。製品固有の2:1値をこの印刷品の合格条件には流用していません。<br><a href="https://docs.robotis.com/docs/dxl/model_reference/x_series/xl_series/xl430-w250/">ROBOTIS: XL430-W250制御資料</a>。外部の力計なしにPresent LoadやPWM値から把持力を確定しません。</p>
</body></html>'''
    (ROOT/'REVIEW_ja.html').write_text(page)
    print('CURRENT CAD GATES PASS',flush=True)

if __name__=='__main__':main()
