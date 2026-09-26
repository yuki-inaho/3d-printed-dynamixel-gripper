from onshape_api import *
from urllib.parse import quote
import sys
mates=json.loads((ROOT/'mates.json').read_text())
mode=sys.argv[1]
for name,r in mates.items():
    if mode=='nolimits' and name not in ['dof_gripper_drive','dof_jaw_left','dof_jaw_right']:continue
    if mode in ['suppress','unsuppress'] and not name.startswith('closing'):continue
    f=r['feature']
    if mode=='nolimits':next(p for p in f['parameters'] if p['parameterId']=='limitsEnabled')['value']=False
    else:f['suppressed']=mode=='suppress'
    res=api(f'/assemblies/d/{DID}/w/{WID}/e/{ASM}/features/featureid/{quote(f["featureId"],safe="")}','POST',{'feature':f})
    print(name,res.get('featureState'))
