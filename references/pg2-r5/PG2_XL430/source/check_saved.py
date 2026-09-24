"""Inspect the serialized STEP assemblies, not only in-memory construction objects."""
from design import *
from camera import optional_parts
from assembly_reader import read_step
from guardrails import geometry
from review_iteration import inspect
from types import SimpleNamespace
import json
m=Model();checks=[]
for name,a,camera in [('PG2_open',30,False),('PG2_mid',90,False),('PG2_closed',140,False),('PG2_camera_optional',30,True)]:
    expected=m.at(a)+(optional_parts() if camera else [])
    md={x.name:x for x in expected}
    _,_,got=read_step(str(ROOT/'CAD'/f'{name}.step'))
    assert len(got)==len(expected),(name,len(got),len(expected))
    actual=[Part(q.name,q.world,md[q.name].color,md[q.name].group,md[q.name].material,md[q.name].role) for q in got]
    geometry(m,actual)
    result=inspect(SimpleNamespace(at=lambda angle:actual,p=P),[a])
    result.update(file=name+'.step',occurrences=len(got),pass_=not result['collisions'])
    checks.append(result);print(name,result['pass_'],flush=True)
r={'pass':all(x['pass_'] for x in checks),'checks':checks}
(ROOT/'reports/saved_step_collisions.json').write_text(json.dumps(r,indent=2))
