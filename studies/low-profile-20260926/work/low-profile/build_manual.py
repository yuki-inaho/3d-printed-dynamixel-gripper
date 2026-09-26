"""Build the human guide with local screenshots embedded; no remote assets."""

import base64
import json
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/low-profile-250g"


def main():
    chunks = (OUT / "MANUAL.md").read_text().split("\n---\n")
    sections, toc = [], []
    for number, chunk in enumerate(chunks, 1):
        body = markdown.markdown(chunk, extensions=["tables", "fenced_code"])
        title = re.search(r"<h[12]>(.*?)</h[12]>", body).group(1)
        toc.append(f'<a href="#p{number}">{title}</a>')

        def embed(match):
            data = base64.b64encode((OUT / match.group(1)).read_bytes()).decode()
            return f'src="data:image/png;base64,{data}"'

        body = re.sub(r'src="(images/[^\"]+)"', embed, body)
        cls = "multi" if body.count("<img ") > 1 else "single"
        sections.append(
            f'<section class="page {cls}" id="p{number}"><div class="running">D405 LOW PROFILE · ON-SCREEN OPERATIONS & VALIDATION</div><article>{body}</article><footer>2026-09-26 · Free / Public · Kinematics only <span>{number} / {len(chunks)}</span></footer></section>'
        )
    css = """*{box-sizing:border-box}body{margin:0;background:#e9eff0;color:#19313c;font:13px/1.65 "Noto Sans CJK JP",sans-serif}nav{position:fixed;inset:0 auto 0 0;width:260px;background:#123743;color:#fff;overflow:auto;padding:22px 18px}nav a{display:block;font-size:12px;color:#daeeec;padding:6px 0;border-bottom:1px solid #355562;text-decoration:none}nav button{margin:14px 0;padding:10px;border:0;background:#b9e9d8;cursor:pointer}main{margin-left:280px;padding:25px 0}.page{width:186mm;height:270mm;background:white;margin:0 auto 25px;padding:15px 20px 42px;position:relative;box-shadow:0 3px 18px #173b4320}.running{font-size:9px;letter-spacing:1.1px;border-bottom:2px solid #268872;padding-bottom:7px;color:#5d7f86}h1{font-size:30px;line-height:1.4}h2{font-size:21px;line-height:1.5;margin:15px 0 12px;color:#124b59}p{margin:10px 0}li{margin:6px 0}ol,ul{padding-left:23px}a{color:#116b8d;overflow-wrap:anywhere}code{font:11px/1.5 "Noto Sans Mono CJK JP",monospace;overflow-wrap:anywhere}pre{white-space:pre-wrap;background:#edf4f5;border-left:3px solid #298b7c;padding:12px;line-height:1.5}table{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0}th,td{border:1px solid #c5d8dc;padding:6px 8px}th{background:#e3f1ea;text-align:left}img{display:block;max-width:100%;max-height:420px;object-fit:contain;margin:12px auto;border:1px solid #cddadf;cursor:zoom-in}.multi img{max-height:230px}footer{position:absolute;left:20px;right:20px;bottom:13px;border-top:1px solid #cddade;padding-top:5px;font-size:9px;color:#68848b}footer span{float:right}dialog{border:0;padding:8px;background:#142e38;max-width:96vw;max-height:95vh}dialog img{max-height:90vh;max-width:92vw;margin:0;cursor:zoom-out}dialog::backdrop{background:#001018d9}@page{size:A4;margin:12mm}@media print{body{background:white}nav,dialog{display:none!important}main{margin:0;padding:0}.page{box-shadow:none;margin:0;width:186mm;height:270mm;break-after:page}.page:last-child{break-after:auto}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}@media screen and (max-width:1000px){nav{position:static;width:100%;max-height:220px}main{margin:0;padding:12px}.page{max-width:100%;height:auto;min-height:270mm}}"""
    script = """const d=document.querySelector('dialog');document.querySelectorAll('article img').forEach(i=>i.onclick=()=>{d.querySelector('img').src=i.src;d.querySelector('img').alt=i.alt;d.showModal()});d.onclick=()=>d.close();"""
    html = (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>D405低配置・画面操作マニュアル</title><style>'
        + css
        + '</style></head><body><nav><h2 style="color:white">D405低配置<br>操作マニュアル</h2><p>画像クリックで拡大</p><button onclick="window.print()">印刷 / PDF</button>'
        + "".join(toc)
        + "</nav><main>"
        + "".join(sections)
        + '</main><dialog><img alt="拡大画像"></dialog><script>'
        + script
        + "</script></body></html>"
    )
    (OUT / "MANUAL.html").write_text(html)
    print(json.dumps({"sections": len(chunks), "bytes": len(html.encode())}))


if __name__ == "__main__":
    main()
