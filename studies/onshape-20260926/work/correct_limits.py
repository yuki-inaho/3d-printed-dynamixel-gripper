from onshape_api import *
from joint_definitions import JOINTS
from urllib.parse import quote
mates=json.loads((ROOT/'mates.json').read_text())
for j in JOINTS:
    if 'limits' not in j:continue
    name='dof_'+j['name'];f=mates[name]['feature']
    for p in f['parameters']:
        if p.get('btType')=='BTMParameterNullableQuantity-807':p.update(isNull=True,expression='')
    next(p for p in f['parameters'] if p['parameterId']=='limitsEnabled')['value']=True
    field,unit=('limitZ','mm') if j['type']=='SLIDER' else ('limitAxialZ','deg')
    for suffix,val in zip(['Min','Max'],j['limits']):
        next(p for p in f['parameters'] if p['parameterId']==field+suffix).update(isNull=False,expression=f'{val:.12g} {unit}',value=val,units='millimeter' if unit=='mm' else 'degree')
    f['parameters']=[p for p in f['parameters'] if not p['parameterId'].startswith('limit') or p['parameterId'] in ['limitsEnabled',field+'Min',field+'Max']]
    r=api(f'/assemblies/d/{DID}/w/{WID}/e/{ASM}/features/featureid/{quote(f["featureId"],safe="")}','POST',{'feature':f})
    print(name,r.get('featureState'),flush=True)
    mates[name]=r
(ROOT/'mates.json').write_text(json.dumps(mates,indent=2))
