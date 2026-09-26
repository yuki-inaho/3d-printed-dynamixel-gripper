import json
import os
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parent
target=Path(os.environ.get('ONSHAPE_EXPORT_TARGET',str(root.parent/'outputs/robot')))
k=json.loads((root/'onshape-key-private.json').read_text())['data']
env=os.environ.copy()
env.update(ONSHAPE_API='https://cad.onshape.com',ONSHAPE_ACCESS_KEY=k['accessKey'],ONSHAPE_SECRET_KEY=k['secretKey'])
with Path(os.environ.get('ONSHAPE_EXPORT_LOG',str(root/'export.log'))).open('w') as log:
    p=subprocess.run(['onshape-to-robot',str(target)],env=env,cwd=root,stdout=log,stderr=subprocess.STDOUT)
print('Exporter exit',p.returncode)
raise SystemExit(p.returncode)
