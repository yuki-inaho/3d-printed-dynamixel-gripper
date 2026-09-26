import base64
import json
import re
from pathlib import Path

import markdown

root = Path(__file__).resolve().parents[2]
man = root / "outputs/manual"
source = (man / "MANUAL.md").read_text()
chunks = source.split("\n---\n")
sections = []
toc = []
for i, chunk in enumerate(chunks):
    body = markdown.markdown(chunk, extensions=["tables", "fenced_code"])
    title = re.search(r"<h[12]>(.*?)</h[12]>", body).group(1)
    toc.append(f'<a href="#page-{i + 1}">{title}</a>')
    count = body.count("<img ")
    cls = "cover" if i == 0 else ("multi" if count > 1 else "single")

    def embed(m):
        path = man / m.group(1)
        return 'src="data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode() + '"'

    body = re.sub(r'src="(images/[^\"]+)"', embed, body)
    sections.append(
        f'<section class="page {cls}" id="page-{i + 1}"><div class="running">ONSHAPE ROBOT WORKFLOW · HUMAN GUIDE</div><div class="content">{body}</div><footer>2026-09-26　Free / Public　<span>{i + 1} / {len(chunks)}</span></footer></section>'
    )
css = """
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#e9eef0;color:#152a35;font-family:"Noto Sans CJK JP",sans-serif;font-size:13px;line-height:1.72}nav{position:fixed;inset:0 auto 0 0;width:260px;background:#102e3b;color:white;overflow:auto;padding:26px 18px}nav strong{display:block;font-size:20px;margin-bottom:16px}nav a{color:#d7e7ed;text-decoration:none;display:block;font-size:12px;padding:6px 0;border-bottom:1px solid #294651}nav button{width:100%;padding:9px;background:#a5dfcd;color:#102e3b;border:0;border-radius:5px;margin:10px 0;cursor:pointer}main{margin-left:280px;padding:24px 0}.page{background:white;width:186mm;height:270mm;margin:0 auto 24px;padding:14px 18px 35px;box-shadow:0 3px 16px #182a3520;position:relative;overflow:visible}.running{font:600 9px/1.4 sans-serif;letter-spacing:1.8px;color:#61818e;border-bottom:2px solid #20836f;padding-bottom:8px;margin-bottom:16px}h1{font-size:32px;line-height:1.35;color:#123e50;margin:24px 0 10px}h2{font-size:21px;line-height:1.5;color:#123e50;margin:5px 0 14px}h3{font-size:14px;line-height:1.5;color:#16705e;border-left:3px solid #20836f;padding-left:8px;margin:16px 0 8px}p{margin:9px 0}li{margin:4px 0}ol,ul{padding-left:23px;margin:9px 0}a{color:#176c8b;overflow-wrap:anywhere}strong{font-weight:700}code{font-family:"Noto Sans Mono CJK JP",monospace;font-size:11.5px;overflow-wrap:anywhere}pre{font-size:11.5px;line-height:1.55;padding:12px 14px;background:#f0f5f6;border-left:3px solid #4b8799;white-space:pre-wrap;overflow-wrap:anywhere;margin:12px 0}pre code{font-size:inherit}table{border-collapse:collapse;width:100%;font-size:12px;line-height:1.65;margin:12px 0;table-layout:auto}th{text-align:left;background:#e1efeb;font-weight:700}th,td{border:1px solid #cbd9dc;padding:6px 8px;overflow-wrap:anywhere}tr{break-inside:avoid}img{display:block;max-width:100%;max-height:300px;object-fit:contain;margin:10px auto;cursor:zoom-in;border:1px solid #d4dddf}.multi img{max-height:185px}#page-21 img,#page-23 img{max-height:235px}.cover img{max-height:410px}.cover h2{font-size:23px}footer{position:absolute;bottom:12px;left:18px;right:18px;font-size:9px;color:#6b818a;border-top:1px solid #d4dfe2;padding-top:5px}footer span{float:right}dialog{padding:14px;border:0;border-radius:8px;max-width:96vw;max-height:95vh;background:#132e3b}dialog img{max-height:88vh;max-width:92vw;border:0;cursor:zoom-out}dialog::backdrop{background:#001018d9}dialog button{position:absolute;right:12px;top:5px;border:0;background:white;color:black;font-size:24px;cursor:pointer}
@media(max-width:1000px){nav{position:static;width:auto;max-height:260px}main{margin-left:0;padding:12px}.page{max-width:100%;height:auto;min-height:270mm;padding-bottom:45px}}
@page{size:A4;margin:12mm} @media print{body{background:white}nav,dialog{display:none!important}main{margin:0;padding:0}.page{box-shadow:none;margin:0;padding-top:0;break-after:page;width:186mm;height:270mm;max-width:none;min-height:0}.page:last-child{break-after:auto}a{color:#176c8b;text-decoration:none}img{cursor:default}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
"""
js = """const d=document.querySelector('dialog');document.querySelectorAll('main img').forEach(im=>im.onclick=()=>{d.querySelector('img').src=im.src;d.querySelector('img').alt=im.alt;d.showModal()});d.onclick=()=>d.close();"""
page = (
    '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Onshape ロボット作業マニュアル</title><style>'
    + css
    + '</style></head><body><nav><strong>Onshape ロボット<br>作業マニュアル</strong><div>画像をクリックすると拡大できます。</div><button onclick="window.print()">印刷 / PDFに保存</button>'
    + "".join(toc)
    + "</nav><main>"
    + "".join(sections)
    + '</main><dialog><button aria-label="閉じる">×</button><img alt="拡大画像"></dialog><script>'
    + js
    + "</script></body></html>"
)
(man / "MANUAL.html").write_text(page)
print(
    json.dumps(
        {
            "pages": len(chunks),
            "images": len(list((man / "images").glob("*.png"))),
            "html_bytes": len(page.encode()),
        }
    )
)
