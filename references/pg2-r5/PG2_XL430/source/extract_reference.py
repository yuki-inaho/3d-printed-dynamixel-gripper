from pathlib import Path
import sys, json, re
import cadquery as cq
from assembly_reader import read_step, bounds
base=Path('/mnt/data/input_lowcost/low_cost_robot-gripper-camera-lateral-20260922')
sys.path.insert(0,str(base/'skills/cad-reverse-parametric/studies/all_xl430_revision/source'))
from build_all_xl430 import read_assembly_nodes
p=base/'hardware/follower/step/arm.step'
_,_,rows=read_step(p)
nodes=read_assembly_nodes(p)
tag='/Robot Arm v14/XL-430_new v1:1'
loc=nodes[tag].inverse
local=[]
for row in rows:
 if row.path.startswith(tag+'/'):
  s=row.shape.moved(loc*row.loc)
  b=bounds(s)
  print(row.index,row.path, 'bb', [round(x,3) for x in b], 'V',round(s.Volume(),2))
  name=re.sub(r'[^A-Za-z0-9_.-]+','_',f'{row.index:03d}_{row.name.replace(":","_")}')
  cq.exporters.export(s,f'/mnt/data/PG2_XL430/reference/{name}.step')
  local.append({'name':name,'path':row.path,'bounds':b})
Path('/mnt/data/PG2_XL430/reference/source_parts.json').write_text(json.dumps(local,indent=2))
