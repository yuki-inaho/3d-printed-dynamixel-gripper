"""Call Onshape's documented REST API through the existing Playwright login.

No cookies, passwords, or API keys are read or persisted by this helper.
"""
import json
import subprocess
from pathlib import Path

WORK = Path(__file__).resolve().parent
DID = '1f8f316ef4f488303d1c1902'
WID = 'ac6b81ffda999cf35e941d15'
PS = '89d3526e69e5a5b79255aece'
ASM = '282c9739d5fb8e5aa9a89f3f'

def api(path, method='GET', body=None):
    if not path.startswith('/api/'):
        raise ValueError('Expected Onshape API path')
    args = dict(method=method, headers={'Content-Type':'application/json'})
    if body is not None:
        args['body'] = json.dumps(body)
    code = f'async () => {{ const r=await fetch({json.dumps(path)},{json.dumps(args)}); const t=await r.text(); return {{status:r.status,text:t}}; }}'
    p = subprocess.run(['rtk','proxy','npx','--yes','@playwright/cli','-s=onshape','--raw','eval',code],cwd=WORK,text=True,capture_output=True,timeout=120)
    if p.returncode:
        raise RuntimeError(p.stdout+p.stderr)
    result=json.loads(p.stdout)
    if result['status'] >= 400:
        raise RuntimeError(f'{method} {path}: {result["status"]}: {result["text"][:2000]}')
    try:
        return json.loads(result['text'])
    except json.JSONDecodeError:
        return result['text']

if __name__ == '__main__':
    import sys
    result=api(sys.argv[1], sys.argv[3] if len(sys.argv)>3 else 'GET', json.loads(Path(sys.argv[4]).read_text()) if len(sys.argv)>4 else None)
    Path(sys.argv[2]).write_text(json.dumps(result,indent=2))
    print(f'Saved {sys.argv[2]} ({len(json.dumps(result))} JSON characters)')
