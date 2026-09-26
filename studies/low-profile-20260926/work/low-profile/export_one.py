"""Export an already defined native pose via the standard browser dialog."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'outputs/low-profile-250g'
parser=argparse.ArgumentParser()
parser.add_argument('name')
parser.add_argument('--dialog-open', action='store_true')
parser.add_argument('--final-version', action='store_true')
args=parser.parse_args()
targets=json.loads((OUT/'reports/native-pose-targets.json').read_text())['cases']
assert args.name in {r['name'] for r in targets}
body=(HERE/'export-step-dialog.js').read_text()
body=body.replace('low-profile-zero', 'low-profile-'+args.name).replace('native-poses/zero.', 'native-poses/'+args.name+'.').replace("pose:'zero'", "pose:"+json.dumps(args.name)).replace('onshape-step-export-settings.png','onshape-step-export-'+args.name+'.png')
if args.final_version:
    assert args.name=='zero' and args.dialog_open
    body=body.replace('native-poses/zero.','final-version.').replace('low-profile-zero','low-profile-V2-final').replace('onshape-step-export-zero.png','onshape-step-export-v2.png').replace('pose:"zero"','pose:"version_zero"')
if not args.dialog_open:
    prefix='''
  const name=__NAME__;
  if(!await page.locator('[data-parameter-id=namedPositionParameterValue] input').count()){
    await page.locator('[data-bs-original-title="Named positions"]').click();
  }
  await page.locator('[data-parameter-id=namedPositionParameterValue] input').first().waitFor();
  const rows=await page.locator('[data-parameter-id=namedPositionParameterValue] input').evaluateAll(es=>es.map(e=>({name:e.value,id:e.closest('.os-tr').getAttribute('data-id')})));
  for(const desired of name==='zero'?['zero']:['zero',name]){
    const row=rows.find(r=>r.name===desired);
    if(!row)throw new Error('Missing named position '+desired);
    const cell=page.locator('.os-tr[data-id="'+row.id+'"] .os-td').filter({has:page.locator('[data-parameter-id=namedPositionParameterValue]')});
    await cell.click({button:'right'});
    await page.getByRole('menu').waitFor();
    const apply=page.getByText('Apply named position',{exact:true});
    if(await apply.isVisible()){
      await apply.click();
      await page.waitForFunction(n=>document.body.innerText.includes(n+' is applied.')||document.body.innerText.includes(n+' could not'),desired,{timeout:30000});
      if((await page.locator('body').innerText()).includes(desired+' could not'))throw new Error('Solver failed '+desired);
      await page.waitForTimeout(2000);
    }else await page.keyboard.press('Escape');
  }
  await page.locator('.os-tab-name').filter({hasText:'Low Profile D405 - Motion and URDF'}).click({button:'right'});
  await page.getByText('Export…',{exact:true}).click();
'''.replace('__NAME__',json.dumps(args.name))
    body=body.replace('async page => {','async page => {'+prefix,1)
script=HERE/'current-export.js'
script.write_text(body)
proc=subprocess.run(['rtk','proxy','npx','--yes','@playwright/cli','-s=onshape-headless','run-code','--filename=low-profile/current-export.js'],cwd=ROOT/'work',capture_output=True,text=True,timeout=600)
raw=proc.stdout+proc.stderr
log=HERE/'ui-logs'/('export-'+args.name+'.txt')
if log.exists():
    index=1
    while log.with_name(log.stem+'-attempt-'+str(index)+'.txt').exists():
        index+=1
    log.rename(log.with_name(log.stem+'-attempt-'+str(index)+'.txt'))
log.write_text(raw)
if proc.returncode or '### Error' in raw:
    raise RuntimeError(raw[-4000:])
result=json.loads(raw.split('### Result\n',1)[1].split('\n###',1)[0])
p=Path(result['path'])
assert p.is_file() and p.stat().st_size>1000 and result['error'] is None
result.update(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
manifest=OUT/'reports/ui-export-manifest.json'
data=json.loads(manifest.read_text()) if manifest.exists() else {'direct_api_calls':0,'exports':[]}
data['exports'].append(result)
manifest.write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(result,indent=2),flush=True)
