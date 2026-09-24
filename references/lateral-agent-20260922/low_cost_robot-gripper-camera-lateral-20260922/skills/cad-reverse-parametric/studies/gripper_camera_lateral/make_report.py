"""Build a self-contained Japanese review HTML and overview from verified CAD renders.
Run after source/study.py build. Extra front/exploded views are rendered if missing.
"""
from __future__ import annotations
import base64
import html
import io
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

STUDY=Path(__file__).resolve().parent
sys.path.insert(0,str(STUDY/'source'))
from design import DEFAULT_OUT,build,hand_items,camera_basis,cq
from render_cad import render


def extras(out):
    p=out/'preview'
    if (p/'hand_front_50deg.png').exists() and (p/'camera_exploded.png').exists():return
    d=build();items=hand_items(d,50)
    render([(i.world,i.color) for i in items if i.shape.Solids()],p/'hand_front_50deg.png',direction=(1,1,1),size=(1600,1200))
    f=camera_basis(d.config)[2]
    shifts={'wrist_camera_bridge':0,'uvc28_camera_carrier':12,'uvc28_pcb_spacer_4mm':22,
            'ASSUMED_camera_pcb':32,'ASSUMED_lens_envelope':32,'ASSUMED_back_electronics':32}
    render([(i.world.moved(cq.Location(tuple(f*shifts[i.key]))),i.color) for i in d.in_hand(d.items) if i.key in shifts],
           p/'camera_exploded.png',direction=(1,1,1),size=(1300,1000))


def img64(path):
    im=Image.open(path).convert('RGB');im.thumbnail((1300,1100))
    bio=io.BytesIO();im.save(bio,'JPEG',quality=90)
    return 'data:image/jpeg;base64,'+base64.b64encode(bio.getvalue()).decode()


def overview(out):
    p=out/'preview';canvas=Image.new('RGB',(2000,1630),'#ffffff');draw=ImageDraw.Draw(canvas)
    font='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
    def ft(n):
        try:return ImageFont.truetype(font,n)
        except OSError:return ImageFont.load_default(size=n)
    def text(x,y,s,size=27,color='#243342'):draw.text((x,y),s,font=ft(size),fill=color)
    text(70,42,'横開きジョー ＋ 手首カメラ',58)
    text(72,125,'既存形状を保つ90°組み替え案  |  2026-09-22',28,'#576575')
    draw.rounded_rectangle((1370,60,1930,130),radius=14,fill='#fff0d8')
    text(1405,74,'試作設計・実機製作は未承認',29,'#805019')
    im=Image.open(p/'hand_front_50deg.png').convert('RGB');a=np.asarray(im).astype(int)
    bg=a[0,0];mask=np.max(abs(a-bg),axis=2)>20;yy,xx=np.where(mask)
    im=im.crop((max(0,xx.min()-30),max(0,yy.min()-30),min(im.width,xx.max()+30),min(im.height,yy.max()+30)))
    im=ImageOps.contain(im,(1090,820));canvas.paste(im,(50+(1090-im.width)//2,200+(820-im.height)//2))
    text(1190,238,'変更点',36)
    lines=[('01','元のジョーを手首で90°組み替え'),('02','4 mmフランジとカメラ支持部を追加'),('03','28×28 mm穴の交換式キャリア')]
    for j,(num,s) in enumerate(lines):
        y=320+j*96;text(1190,y,num,30,'#b66d13');text(1252,y+1,s,27)
    text(1190,648,'検証済みの範囲',34)
    for j,s in enumerate(['閉じ／50°開き：全腕の外部干渉 0', '両指先端の視認性：51姿勢で合格', '新規3部品：STEP／STL整合・閉鎖性', '基準：混在サーボ版（全XL430版ではない）']):
        text(1190,718+j*57,s,25)
    text(74,1023,'仮想カメラからの見え方',38)
    text(620,1036,'水平60°／垂直45°の仮定。実カメラは未校正。',25,'#576575')
    for j,angle in enumerate([0,25,50]):
        x=70+j*646
        cam=ImageOps.contain(Image.open(p/f'camera_{angle}deg.png').convert('RGB'),(615,461))
        canvas.paste(cam,(x,1100));draw.rectangle((x,1100,x+614,1560),outline='#d4dce3',width=2)
        text(x+20,1110,f'{angle}° 開き',27)
    text(75,1581,'緑：固定指　青：可動指　橙：新規支持部　｜　固定指＋回転指の機構を維持。平行ジョー化ではありません。',23,'#576575')
    canvas.save(out/'overview.png')


def main():
    out=DEFAULT_OUT;extras(out);overview(out)
    r=json.loads((out/'reports/validation.json').read_text())
    assert r['geometry_passed']
    p=out/'preview'
    images={str(a):img64(p/f'camera_{a}deg.png') for a in [0,25,50]}
    h='''<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>横開きジョー＋手首カメラ｜設計レビュー</title><style>
:root{--ink:#253342;--muted:#657180;--line:#dae1e7;--accent:#b66d13;--paper:#f5f7fa}*{box-sizing:border-box}body{margin:0;color:var(--ink);font-family:system-ui,-apple-system,"Noto Sans CJK JP","Yu Gothic",sans-serif;line-height:1.85;background:var(--paper)}main{max-width:1180px;margin:auto;padding:48px 28px}h1{font-size:clamp(27px,4vw,45px);line-height:1.35;letter-spacing:.01em;margin:12px 0 18px}h2{font-size:26px;margin:0 0 20px}h3{font-size:19px}.kicker{letter-spacing:.14em;font-weight:700;color:var(--accent);font-size:13px}.sub{color:var(--muted);max-width:940px}section{background:white;border:1px solid var(--line);border-radius:18px;padding:32px;margin:28px 0}.badge{display:inline-block;padding:7px 15px;border-radius:8px;background:#fff0d8;color:#805019;font-weight:700}.grid{display:grid;grid-template-columns:1.25fr 1fr;gap:24px;align-items:center}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}img{max-width:100%;display:block;border-radius:10px}figure{margin:0}figcaption{font-size:14px;color:var(--muted);margin:8px 0 18px}table{border-collapse:collapse;width:100%;font-size:15px}th,td{text-align:left;padding:13px 12px;border-bottom:1px solid var(--line);vertical-align:top}th{background:#f4f6f8}.tablewrap{overflow-x:auto}.pass{color:#257345;font-weight:700}.warn{border-left:4px solid #d79a39;background:#fff8ed;padding:16px 20px;margin:18px 0}.small{font-size:14px;color:var(--muted)}code,pre{font-family:ui-monospace,monospace}code{overflow-wrap:anywhere}pre{background:#172532;color:#e9f0f6;padding:20px;border-radius:10px;overflow:auto;font-size:13px}button{background:white;border:1px solid #acb7c3;border-radius:8px;padding:10px 24px;font:inherit;cursor:pointer;margin:0 7px 15px 0}button.active{background:#253342;color:white;border-color:#253342}details{border-top:1px solid var(--line);padding:18px 0}summary{cursor:pointer;font-weight:600}.metric{font-size:38px;font-weight:800;line-height:1.2;color:#2d6451}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin:25px 0}.source{overflow-wrap:anywhere}.footer{color:var(--muted);font-size:14px;padding:16px 4px}@media(max-width:760px){main{padding:24px 14px}.grid,.grid2{grid-template-columns:1fr}section{padding:22px 18px}.metrics{gap:10px}.metric{font-size:30px}}@media print{section{break-inside:avoid}button{display:none}body{background:white}main{padding:0}}</style></head><body><main>
<div class="kicker">LOW COST ROBOT / CAD REVISION / 2026-09-22</div>
<h1>横開きジョー ＋ 手首カメラ</h1>
<p class="sub">既存の固定指・可動指を作り直さず、手首で90°組み替える設計。カメラの画面左右に指が開き、両指の先端を見ながら把持できる配置を検証しました。</p>
<span class="badge">幾何ゲート PASS ／ 製作・実機投入は未承認</span>
<section><div class="grid"><figure><img src="HERO" alt="横開きグリッパと上方のカメラマウントのCAD"><figcaption>保存した設計と同じB-repから描画した50°開き姿勢。カメラは仮定外形です。</figcaption></figure><div><h2>形状を残して、向きを変える。</h2><p>既存の手首4穴が90°回転対称であることを測定し、グリッパ全体を90°クロック。4 mmのフランジを挟み、支持ブリッジと交換式キャリアを追加しました。</p><p><b>緑＝固定指、青＝可動指、橙＝新規支持部。</b><br>SO-ARMの平行ジョー機構は移植せず、固定指＋回転指の構成を維持しています。</p><div class="warn">基準は <b>XL430×2＋XL330系×4の混在版</b>。未解決干渉のある全XL430版への適合を承認していません。</div></div></div></section>
<section><h2>カメラから、両方の指が見えるか</h2><p>仮定した画角は水平60°・垂直45°、俯角40°。0〜50°を1°刻みで検証し、両指の先端側について、視野内にあることと自己遮蔽を含めた可視面を確認しました。</p><div><button class="active" data-angle="0">0° 閉じ</button><button data-angle="25">25° 開き</button><button data-angle="50">50° 開き</button></div><figure><img id="camera" src="CAM0" alt="閉じ状態の仮想カメラ像"><figcaption id="caption">0°：仮想ピンホールカメラ。画角と焦点は未校正です。画像は視野そのままで、根元の切れを隠していません。</figcaption></figure><p class="small">対象は閉じ姿勢で面重心が元の固定指座標Y≧25 mmにある指先側三角形群。51姿勢の最低可視サンプルは固定指96点／可動指31点。指の根元全体、把持物の陰、反射、解像度、実レンズの歪み・焦点は未保証です。</p></section>
<section><h2>追加する部品は3点</h2><div class="grid"><figure><img src="EXPLODED" alt="カメラキャリアとスペーサーの分解図"><figcaption>分解図。基板・レンズ・背面部品は寸法仮定の表示用外形です。新規ねじは図示していません。</figcaption></figure><div class="tablewrap"><table><tr><th>部品</th><th>役割</th></tr><tr><td>支持ブリッジ</td><td>手首4穴／厚4 mmフランジ／2本の支持脚／結束バンド用窓</td></tr><tr><td>UVC28キャリア</td><td>28×28 mmの基板4穴、中央24 mm開口。M3想定2本で交換</td></tr><tr><td>4 mmスペーサー</td><td>基板背面の部品空間を確保。実基板は要採寸</td></tr></table><p>新設プラスチックのソリッド体積合計は <b>10.850 cm³</b>。質量・強度・造形条件は未確定です。</p><p class="small">RealSense等の専用キャリアは未実装です。28 mm穴ピッチだけで特定カメラへの適合を保証しません。</p></div></div></section>
<section><h2>保存したSTEPで再検証</h2><div class="metrics"><div><div class="metric">0</div>外部干渉<br><span class="small">閉じ／50°開きの全腕</span></div><div><div class="metric">51</div>カメラ検証姿勢<br><span class="small">1°刻み、0〜50°</span></div><div><div class="metric">42 + 46</div>自動テスト合格<br><span class="small">新規study＋既存混在版</span></div></div><div class="tablewrap"><table><tr><th>検査</th><th>結果</th><th>範囲と注意</th></tr><tr><td>原形保存</td><td class="pass">PASS</td><td>161末端要素を直接再利用、上流の配置差ゼロ。独立の無変更STEP対照とも照合</td></tr><tr><td>保存済みアセンブリ</td><td class="pass">PASS</td><td>167末端要素／123ソリッド。仮定カメラ外形3点を含む</td></tr><tr><td>全腕B-rep干渉</td><td class="pass">外部0</td><td>閉じ／50°それぞれ374候補を全件計算。サーボ内部116ペアの重複は別集計</td></tr><tr><td>指の運動</td><td class="pass">11姿勢 PASS</td><td>5°刻み、他の関節は固定。全関節の動作保証ではない</td></tr><tr><td>新設部と回転指</td><td class="pass">1.729 mm以上</td><td>0〜50°連続区間での保守的分離下界。新設部だけに対する検証</td></tr><tr><td>STEP／STL</td><td class="pass">3部品 PASS</td><td>単一ソリッド、閉じた正体積メッシュ。スライス・強度・実機嵌合は別</td></tr><tr><td>製作パッケージ</td><td>拒否／終了2</td><td>再検証後も現物証拠がないため未承認。確認フラグだけで通さない</td></tr></table></div><p class="small">既存供給元CADは無変更でもSTEP再保存で微小な質量特性差が出るため、対照を追加。直接の最大体積差は約0.002946%、配置を戻した対照との差は最大約3.64e-12 mm³。頂点・面数・外接箱も照合しています。</p></section>
<section><h2>同じ視点で、変更前後を確認</h2><p class="small">元の固定指座標に対するX/Y/Z方向の比較です。形状の作り替えではなく、取付の90°変更が見えます。カメラ位置と尺度は前後で同じです。</p>COMPARISONS</section>
<section><h2>製作前に確定すること</h2><div class="warn"><b>特に、手首へ4 mmを追加するため、元のねじをそのまま使えるとは限りません。</b> ホーンの有効ねじ深さ・底付き・座面・規格を現物で確認してください。CADの小径穴からねじ込み量を断定していません。</div><p>カメラの型番と実際の外形・画角・焦点、ねじ長と工具経路、印刷材料・積層方向・剛性、USB配線の曲げと全関節動作、実機の嵌合・校正が残っています。仮のM2×10／M3×8は検討候補であり、確定した調達リストではありません。</p><p>ファームウェアとURDFは未変更。工具長が4 mm増え、取付姿勢が90°変わるため、TCP・カメラ外部パラメータ・可動範囲を更新してください。単純に関節指令へ90°を足す指示ではありません。</p></section>
<section><h2>コード・記録・再現方法</h2><p>同梱リポジトリの <code>skills/cad-reverse-parametric/studies/gripper_camera_lateral/</code> にコード、設定、設計意図、組立案を収録。<code>diary/2026-09-22_gripper-camera-lateral.md</code> に試行と判断を記録しました。</p><pre>cd skills/cad-reverse-parametric
python studies/gripper_camera_lateral/source/study.py build
python -m pytest -q studies/gripper_camera_lateral/source/test_gripper_camera.py
python studies/gripper_camera_lateral/source/study.py validate</pre><p class="small">実行環境：Python 3.13.5 / CadQuery 2.8.0。既存uvロック環境のPython取得はDNS不通で失敗したため、ロック環境での再現成功は主張していません。元のロックファイル・hardware・汎用コアは変更していません。入力・コード・CADのハッシュを収録しています。</p><details><summary>検証JSON（一次データ）</summary><pre>RAWJSON</pre></details><details><summary>参照と帰属</summary><p class="source">基準：ユーザー提供 low_cost_robot-fix-cadre-geometry-review-20260918 (2).zip、公開指定ブランチのcad-reverse-parametric SKILL.md。参照：Robonine SO-ARM100-101-Parallel-GripperのREADMEと提供ZIP内docs/assembly-guide.md Step 9。交換式カメラ構成と28×28 mmの穴ピッチを参照し、同プロジェクトのCAD・画像は移植していません。元リポジトリのライセンスを保持します。</p></details></section><div class="footer">2026-09-22 / CAD geometry review prototype / GitHubへのpush・PR作成は未実施。このHTMLは画像・データを内蔵しており、オフラインで閲覧できます。</div></main><script>const frames=IMAGES;document.querySelectorAll('[data-angle]').forEach(b=>b.addEventListener('click',()=>{const a=b.dataset.angle;document.getElementById('camera').src=frames[a];document.getElementById('camera').alt=a+'度開きの仮想カメラ像';document.getElementById('caption').textContent=a+'°：仮想ピンホールカメラ。画角と焦点は未校正です。画像は視野そのままで、根元の切れを隠していません。';document.querySelectorAll('[data-angle]').forEach(x=>x.classList.toggle('active',x===b));}));</script></body></html>'''
    comparisons=''
    for axis in ['X','Y','Z']:
        comparisons+=f'<details><summary>{axis}方向の比較を開く</summary><div class="grid2">'
        for when,label in [('before','変更前・混在版'),('after','変更後・カメラ追加')]:
            comparisons+=f'<figure><img src="{img64(p/f"{when}_{axis}.png")}" alt="{axis}方向{label}"><figcaption>{label}</figcaption></figure>'
        comparisons+='</div></details>'
    h=h.replace('HERO',img64(p/'hand_front_50deg.png')).replace('EXPLODED',img64(p/'camera_exploded.png')).replace('CAM0',images['0'])
    h=h.replace('COMPARISONS',comparisons).replace('RAWJSON',html.escape(json.dumps(r,ensure_ascii=False,indent=2))).replace('IMAGES',json.dumps(images))
    (out/'review_ja.html').write_text(h)
    print(out/'review_ja.html')

if __name__=='__main__':main()
