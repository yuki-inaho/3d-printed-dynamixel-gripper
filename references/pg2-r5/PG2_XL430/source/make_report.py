"""Generate the self-contained Japanese review from issued evidence and work documents.
Uses actual CAD images; no generated concept illustration is substituted.
"""
from pathlib import Path
from html import escape
import base64
import json
import mistune

ROOT=Path(__file__).resolve().parents[1]
md=mistune.create_markdown(plugins=['table'])

def picture(name,caption,css=''):
    p=ROOT/'images'/name
    mime='image/gif' if p.suffix=='.gif' else 'image/png'
    data=base64.b64encode(p.read_bytes()).decode('ascii')
    return f'<figure class="{css}"><img alt="{escape(caption)}" src="data:{mime};base64,{data}"><figcaption>{escape(caption)}</figcaption></figure>'

def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join(f'<th>{escape(str(x))}</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{escape(str(x))}</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def generate():
    dod=json.loads((ROOT/'reports/RELEASE_DOD.json').read_text())
    assert dod['digital_prototype_DoD_pass'] and not dod['physical_acceptance_pass']
    eng=json.loads((ROOT/'reports/engineering_checks.json').read_text())
    neg=json.loads((ROOT/'reports/export_audit.json').read_text())['guardrails']['negative_tests']
    metric=dod['metrics']
    chunks=[]
    chunks.append('''<header><p class="eyebrow">PG2 / R5 · CAMERA C3 · 2026-09-23</p><h1>参照配置に戻した<br>XL430平行2爪グリッパー</h1><p class="lead">背面の縦置きサーボ。前面のクランクと2本のリンク。上下の印刷ガイド。金属案内棒を使わない組立式の試作設計です。</p></header><div class="status"><b>デジタル試作DoD：8項目を完了</b><br>現物の印刷・組立・摩擦・強度・把持力・耐久は未検証です。全腕への互換性も承認していません。</div>''')
    chunks.append(picture('overview.png','最終の実CAD。側面でも、モーターの長辺が縦方向、出力軸と爪の突出方向が同じであることを確認できます。'))
    chunks.append('<nav><a href="#review">前案のレビュー</a><a href="#design">今回の構成</a><a href="#checks">検査と限界</a><a href="#print">印刷・組立</a><a href="#camera">追加カメラ</a><a href="#records">作業書全文</a></nav>')
    chunks.append('<section id="review"><h2>1. 前案を不合格とした理由</h2><p>PG1 R7は「単一サーボで平行開閉」という抽象条件だけを満たし、依頼された外形・配置・部品構成を変えていました。造形精度への対策として金属丸棒を追加する判断も、依頼者が示した方向と一致しません。干渉検査の件数を増やしても、この要求不適合は解消しません。</p>')
    chunks.append(table(['観点','PG1 R7の問題','PG2 R5での是正'],[
      ['モーター配置','出力軸と爪の突出方向が直交する寝かせた配置','XL430の長辺はY。背面に置き、出力と爪突出をともに+Zへ固定'],
      ['案内方式','Ø6×150 mmの金属丸棒と関連部品を追加','印刷した上下の角形案内面と別体押さえ。丸棒・直動軸受・金属カラーなし'],
      ['型番の扱い','XL330という仮定を設計へ持ち込んだ','今回は明示指定のXL430-W250だけを許可'],
      ['検証の優先順位','CAD干渉0を、要求適合や製作しやすさの代わりにした','要求適合→隙間→組立工程→保存データを個別に検査'],
      ['組立・印刷','未確認の加工や工具経路を楽観的に扱った','爪の局所サポートと、カメラの板先行組立を具体的に指定']]))
    chunks.append('<p>参照元はRobot &amp; ChiselのMini Max記事です。記事はAX-12を1台使って両爪を平行に動かす構成を示しています。本案はその配置・機構を参考にした新しい寸法設計で、元データの寸法コピーではありません。<a href="https://www.robotandchisel.com/2011/07/01/new-gripper-for-mini-max/">参照記事</a></p></section>')
    chunks.append('<section id="design"><h2>2. 今回の構成と寸法</h2>')
    chunks.append(table(['項目','最終設定'],[
      ['サーボ','DYNAMIXEL XL430-W250 ×1。枠の背面に縦置き'],['駆動','半径15 mmの対向クランク＋穴中心間36 mmの湾曲リンク2本'],['案内','印刷した矩形摺動面。取り外せる上下の押さえ'],['関節','直径6 mmの印刷一体肩部＋M3ねじ・ナット・座金。別体の金属カラーなし'],['開口','硬い爪同士で約0.80〜50.81 mm。パッドはモデル化していません'],['片爪の移動量','約25.01 mm'],['外形','136×84×75 mm。サーボ・出力部込み、カメラなし'],['本体印刷品','6種類・9個。カメラは別途2個の任意追加品'],['機構角','30〜140°。サーボの絶対指令角とは別'],['左右対称','把持中心はX=0。爪の向きは変わらず直線移動']]))
    chunks.append('<p>黒・灰色が印刷した枠と押さえ、赤橙色が爪、橙色が中央回転板、緑が連接棒です。金属の案内軸はありませんが、標準ねじ・ナット・座金および既製サーボの出力部は使用します。</p>')
    chunks.append(picture('motion.gif','実CADから作成した開閉表示。表示速度は説明用で、実サーボの速度や動作実験を表すものではありません。','motion'))
    chunks.append('<div class="two">'+picture('open_front.png','正面・30°：公称開口50.81 mm')+picture('closed_front.png','正面・140°：公称開口0.80 mm')+'</div>')
    chunks.append('<h3>隙間を残す場所を明示しました</h3><p>標準のZ方向総隙間は0.7 mmで、枠側0.3 mmと押さえ側0.4 mmに分けています。押さえの選択品で総隙間0.5 / 0.9 mmにも変更できます。これは両面の合計で、片側の数値ではありません。押さえねじを緩めて調整する方法は採用していません。</p><p>R4では、体積交差が0でも爪の補強部と押さえ端が接していました。R5で端を1 mm退け、上下に寄った場合も最小0.4 mmの逃げと、最小2.4 mmの抜け止めのかかりを残しました。公称寸法の計算値であり、反り・たわみ・摩耗後の値ではありません。</p><p>開・閉端には印刷した当たり面を設けました。指令範囲から当たり面までの計算余裕は、開側約1.00 mm、閉側約0.29 mmです。小さい側の余裕は印刷誤差に左右されるため、現物で端点を再設定します。当たり面へモーターで押し付け続けてはいけません。</p></section>')
    chunks.append('<section><h2>3. レビュー中に見つかった不合格</h2>')
    chunks.append(table(['発見事項','対応','再発防止'],[
      ['爪の張り出しに対し、案内の支持長が不足気味','爪先Z45→36、支持長24→28 mm','干渉0だけで採用せず、支持形状を別に確認'],
      ['カメラ台が3つのソリッドへ分断','支持腕を回り込ませ、単一ソリッドへ変更','isValidだけでなく印刷品のソリッド数=1を要求'],
      ['保存STEPだけでナット座の交差判定が不整合','二面でナットを保持する角ポケットへ変更','保存後の部品間検査を省略しない'],
      ['視線は通るが仮レンズ筐体が干渉','カメラC3で位置を前方・上方へ変更','光学中心だけでなくカメラの実体積も検査'],
      ['押さえと爪の補強部が体積0の接触','R5で端を退けて1 mmの逃げ','実形状の最短距離検査とゼロ隙間の負例を追加'],
      ['カメラ基板下側2本の工具が台へ接触','基板→独立取付板→台→本体の組立順へ変更','工程別の部品集合を検査し、整備時の板取り外しを明記']]))
    chunks.append('<p>失敗・中断・旧形状は reports/iterations/ に残しています。旧試験の版名を変えて最終版の結果にすることや、許容干渉を追加して不具合を隠すことはしていません。</p></section>')
    chunks.append('<section id="checks"><h2>4. 完了条件と検査範囲</h2>')
    chunks.append(table(['DoD','確認内容','最終判定'],[(d['id'],d['result'],'デジタル試作として合格') for d in dod['DoD']]))
    chunks.append(table(['主な実測・検査','結果'],[
      ['実形状の開閉走査','30〜140°・1°刻み111姿勢。不許可の体積干渉0'],['案内の最短距離','枠0.20 mm、上下押さえ0.40 mm。標準0.7 mm品の全111姿勢'],['保存後の組立検査','4ファイル。単体は各55要素、カメラ付き75要素'],['出力ファイル','STL12点：閉メッシュ、正体積、法線整合、境界辺・非多様体辺なし。STEP16点：再読込妥当性'],['機構計算','0.1°刻み1101点。単調な開閉、穴間距離整合'],['意図的違反','12種類すべてを拒否。型番・実姿勢・実軸・金属棒・ゼロ隙間等'],['工具','作業書の工程ごとに工具軸32件。カメラ基板は台を付ける前'],['追加カメラ','理想画角80°水平・64.37°垂直。3姿勢、爪先接触面の54本の視線']]))
    chunks.append('<div class="note"><b>この検査が証明していないこと</b><p>角度は離散点であり、連続した全軌道の証明ではありません。可動走査は標準総隙間0.7 mm品が対象です。選択品0.5/0.9 mmは個別の形状健全性を確認しています。工具は軸部分で、持ち手や作業者の手を含みません。サーボ内部は参考品1組として扱い、内部の重複を検証対象にしていません。</p><p>外部で許容した形状重複は、ケース側面の4本のセルフタップねじと既存下穴の組合せだけです。ねじ山・刃先・摩擦はモデル化していません。プリンタの成功率、把持力、繰返し精度、耐久寿命、全腕互換を保証しません。</p></div>')
    chunks.append('<h3>要求追跡</h3>'+table(['要求','実装','対応DoD'],[(d['requirement'],d['implementation'],' / '.join(d['evidence'])) for d in dod['requirements']]))
    chunks.append('<details><summary>12種類の負例検査</summary>'+table(['意図的な違反','結果'],[(d['test'],'拒否を確認') for d in neg])+'</details></section>')
    chunks.append('<section id="print"><h2>5. 印刷と組立</h2>')
    chunks.append(picture('print_layout.png','STLへ保存した実際の印刷姿勢。各図の縮尺は別です。支え自体は表示していません。'))
    chunks.append('<p><b>最初は09・10の試験片だけを印刷します。</b> 試験片で隙間を選んだあと、本体を作業書の数量で印刷します。標準本体9個、追加カメラ2個であり、12種類のファイルを1個ずつ出力する手順ではありません。</p><p>爪03は側面印刷で、根元の非摺動端面への局所サポートが必要です。追加カメラ台も局所サポートの確認が必要です。完全なサポート不要や、高い製作成功率が検証された設計とは扱っていません。長い枠の反りは小さい試験片だけでは再現できません。</p>')
    chunks.append(picture('exploded.png','組立関係の分解表示。標準ねじ・ナット・座金はこの図からのみ省略しています。組立STEPには含みます。'))
    chunks.append('<p>基本順序は、試験片→モーターと背面取付部→枠→出力部と回転板→爪と押さえ→リンクです。リンクを付ける前に左右の爪を手で滑らせ、案内の引っ掛かりを確認します。サーボを無理に逆駆動する検査ではありません。</p><h3>XL430のケースねじは区別が必要です</h3><p>メーカー図の側面取付ねじはPHS M2.6×5 TAPです。本案の座面ではケースへ2.75 mm入る配置で、メーカーが示す使用深さ上限4 mmより短くしています。通常のM2.5機械ねじへの置換や、ケース分解用ねじの抜き替えはしません。出力部には専用の3 mm座面とM2×6を組み合わせ、侵入を3 mmにしています。ねじ長の変更時は現物とメーカー図を再確認してください。</p><p>電源仕様は6.5〜12.0 V、推奨11.1 Vです。前案XL330の5 V説明を流用しないでください。絶対サーボ角と機構角を対応させ、初回は低速度・低いPWM上限・無負荷で確認します。動作域へ指を入れず、停止したまま押し続けません。</p><p class="source">根拠：<a href="https://docs.robotis.com/docs/dxl/model_reference/x_series/xl_series/xl430-w250/">ROBOTIS公式仕様</a> ／ <a href="https://emanual.robotis.com/assets/images/dxl/x/assembly/xl430/etc/xl430_etc_assembly_example_side.jpg">側面ねじ図</a> ／ <a href="https://emanual.robotis.com/assets/images/dxl/x/assembly/xl430/etc/xl430_4mm_mount_warning.png">深さ上限</a> ／ <a href="https://emanual.robotis.com/assets/images/dxl/x/assembly/xl430/xl_xc430_warning.png">出力部のねじ長注意</a>。2.75 / 3 mmは本案の計算値です。</p></section>')
    chunks.append('<section id="camera"><h2>6. カメラは任意の追加品</h2>')
    chunks.append(picture('camera_optional.png','C3：短い台と交換式取付板。仮定した基板・レンズの外形を含みます。実カメラの適合は未承認です。'))
    chunks.append('<p>32×32×1.6 mm基板・28 mm穴ピッチ・65°下向きの固定台です。本体上桟の前へレンズを出し、長い後方支柱を使いません。カメラなしでもグリッパー本体は完成します。</p><p><b>基板を取付板08へ固定してから、台07へ取り付けます。</b> 台を付けた状態では下側の基板ねじ2本へ工具が通りません。基板の整備は後側のM3×12を外し、板を台から取り外して行います。最後にカメラ一式を本体へM3×16の2本で固定します。</p><p>54本の視線検査は、3姿勢の爪先側の接触面を対象にしています。実際の最短撮影距離、ピント、歪み、コネクタ、USB配線、把持物の遮蔽、爪全体の視認は未検証です。</p></section>')
    chunks.append('<section id="records"><h2>7. 作業書・数量・未完項目</h2><p>以下は納品ファイルの本文です。作業書には良かった点だけでなく、不合格を見つけた経緯も残しています。</p>')
    for name,title in [('ASSEMBLY_AND_PRINT_ja.md','印刷・部品表・組立作業書 全文'),('WORK_ORDER_ja.md','辛口レビュー・凍結要求・作業履歴 全文'),('PHYSICAL_ACCEPTANCE_ja.md','現物の受入項目 — すべて未実施')]:
        chunks.append('<details><summary>'+title+'</summary><div class="document">'+md((ROOT/'docs'/name).read_text())+'</div></details>')
    chunks.append('</section><section><h2>8. ファイルと再生成</h2><p>組立の確認にはCAD/のSTEP、印刷にはSTL/を使います。source/に再生成・検査プログラム、reference/に添付由来のモーター形状、reports/に数値結果があります。元のPG1、元リポジトリのhardware、URDF、制御ソフトは変更していません。GitHubへの書込みもしていません。</p><p>ソースや形状を変更した場合は、その変更に対応する検査を再実行してください。release_gate.pyは結果の版・件数・判定・時刻を照合して公開を止め、MANIFEST.sha256は納品ファイルの内容を固定します。禁止例検査は指定した12例に対するもので、未知の誤設計をすべて自動検出する保証ではありません。</p><p>本体の既存アームへの取付板・全腕の衝突・工具座標は未承認です。前案の取付形状を流用して成立すると見なしていません。次の物理的な工程は、試験片09・10の造形と実際の嵌合確認です。</p></section>')
    css='''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#edf0f3;color:#202b36;font-family:system-ui,"Noto Sans CJK JP",sans-serif;line-height:1.85}main{max-width:1140px;margin:28px auto;padding:48px 56px;background:#fff}header{padding:8px 0 20px}.eyebrow{font-size:13px;letter-spacing:.13em;color:#596b78}h1{font-size:38px;line-height:1.35;margin:14px 0 22px}h2{font-size:25px;line-height:1.5;border-top:2px solid #dfe6eb;padding-top:23px;margin-top:48px}h3{font-size:19px;margin-top:30px}.lead{font-size:18px;max-width:880px}.status{background:#e8f2ed;border-left:5px solid #34755a;padding:16px 21px}.note{background:#f5f2eb;border-left:4px solid #aa8750;padding:16px 22px;margin-top:24px}.note p{margin-bottom:0}figure{margin:26px 0}img{width:100%;height:auto;display:block}figcaption{font-size:13px;line-height:1.65;color:#5b6974;margin:8px 0 0}.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}.motion{max-width:800px;margin:24px auto}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px;margin:18px 0}th,td{border:1px solid #d8e0e6;padding:11px 13px;vertical-align:top;text-align:left}th{background:#edf2f5}td:first-child{min-width:110px}tr:nth-child(even) td{background:#f9fafb}nav{display:flex;gap:14px;flex-wrap:wrap;border-top:1px solid #d8e0e6;border-bottom:1px solid #d8e0e6;padding:14px 0;font-size:14px}a{color:#266486;overflow-wrap:anywhere}.source{font-size:13px;color:#52616c}details{border:1px solid #d9e1e7;margin:16px 0;padding:12px 17px}summary{cursor:pointer;font-weight:650}.document{font-size:15px}.document h1{font-size:25px}.document h2{font-size:21px}.document pre{overflow-x:auto}.document li{margin:10px 0}code{overflow-wrap:anywhere;font-size:.95em}footer{font-size:13px;color:#61707b;border-top:1px solid #d9e1e7;margin-top:42px;padding-top:18px}@media(max-width:760px){main{margin:0;padding:24px 19px}h1{font-size:29px}h2{font-size:23px}.two{grid-template-columns:1fr}td,th{padding:8px;font-size:13px}.lead{font-size:16px}}@media print{body{background:white}main{margin:0;padding:0}nav{display:none}h2,h3{break-after:avoid}figure,tr{break-inside:avoid}details{break-inside:auto}}'''
    out='<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PG2 R5 — XL430縦置き・印刷ガイド設計レビュー</title><style>'+css+'</style></head><body><main>'+''.join(chunks)+'<footer>PG2 R5 / Camera C3 · 図は実CAD由来 · 公開範囲：デジタル試作 · 現物受入：未実施</footer></main></body></html>'
    (ROOT/'PG2_design_review_ja.html').write_text(out,encoding='utf-8')
    print('Wrote self-contained review:',len(out.encode('utf-8')),'bytes')

if __name__=='__main__':generate()
