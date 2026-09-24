import sys,json,time
from design import *
from camera import optional_parts
from guardrails import geometry
from review_iteration import inspect
idx,start,end=map(int,sys.argv[1:4]);m=Model();m.fixed+=optional_parts();geometry(m)
t=time.monotonic();r=inspect(m,list(range(start,end+1)));r['seconds']=time.monotonic()-t
r['all_parts_including_camera']=True
(ROOT/f'reports/sweep_{idx}.json').write_text(json.dumps(r,indent=2))
print('FINISHED',idx,len(r['collisions']),flush=True)
