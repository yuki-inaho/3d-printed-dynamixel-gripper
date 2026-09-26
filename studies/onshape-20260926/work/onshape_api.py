"""Signed Onshape REST calls; private credentials stay outside deliverables."""
import base64
import hashlib
import hmac
import json
import secrets
import os
import urllib.request
import urllib.parse
from email.utils import formatdate
from pathlib import Path

PRIVATE_ROOT=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('ONSHAPE_TASK_WORK',str(PRIVATE_ROOT)))
OUTPUT=Path(os.environ.get('ONSHAPE_TASK_OUTPUT',str(PRIVATE_ROOT.parent/'outputs')))
DID='1f8f316ef4f488303d1c1902'
WID='ac6b81ffda999cf35e941d15'
PS='89d3526e69e5a5b79255aece'
ASM='282c9739d5fb8e5aa9a89f3f'
if (ROOT/'project.json').exists():
    _project=json.loads((ROOT/'project.json').read_text())
    DID,WID,PS,ASM=(_project[k] for k in ('did','wid','ps','asm'))

def api(path, method='GET', body=None, query=None, binary=False):
    credentials=json.loads((PRIVATE_ROOT/'onshape-key-private.json').read_text())['data']
    if not path.startswith('/api/'):
        path='/api/v17'+path
    nonce=secrets.token_hex(16)
    date=formatdate(usegmt=True)
    q=urllib.parse.urlencode(query or {})
    ctype='application/json'
    canonical='\n'.join([method,nonce,date,ctype,path,q,'']).lower().encode()
    digest=base64.b64encode(hmac.new(credentials['secretKey'].encode(),canonical,hashlib.sha256).digest()).decode()
    headers={'Content-Type':ctype,'Accept':'application/json','Date':date,'On-Nonce':nonce,'Authorization':f'On {credentials["accessKey"]}:HmacSHA256:{digest}'}
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request('https://cad.onshape.com'+path+('?' + q if q else ''),data=data,headers=headers,method=method)
    counter=PRIVATE_ROOT/'api-count.txt'
    count=int(counter.read_text()) if counter.exists() else 0
    if count>=1500:
        raise RuntimeError('Task API budget exhausted; stop and inspect')
    counter.write_text(str(count+1))
    try:
        with urllib.request.urlopen(req,timeout=120) as response:
            result=response.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{method} {path}: {e.code}: {e.read().decode()[:2500]}') from None
    if binary:
        return result
    return json.loads(result) if result else None

def save(name, data):
    (ROOT/name).write_text(json.dumps(data,indent=2))

if __name__=='__main__':
    import sys
    result=api(sys.argv[1])
    save(sys.argv[2],result)
    print('saved',sys.argv[2])
