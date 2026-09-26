from onshape_api import *
from urllib.parse import quote

ledger=ROOT/'mates.json'
mates=json.loads(ledger.read_text())
bad=json.loads((ROOT/'last-mate.json').read_text())
if bad['feature']['name']=='closing_left':mates['closing_left']=bad
for name,r in mates.items():
    f=r['feature']
    param=next(p for p in f['parameters'] if p['parameterId']=='primaryAxisAlignment')
    if not param['value'] and r['featureState']['featureStatus']=='OK':continue
    param['value']=False
    result=api(f'/assemblies/d/{DID}/w/{WID}/e/{ASM}/features/featureid/{quote(f["featureId"],safe="")}','POST',{'feature':f})
    mates[name]=result
    ledger.write_text(json.dumps(mates,indent=2))
    print(name,result.get('featureState'),flush=True)
