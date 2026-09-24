from design import *
from camera import *
from review_iteration import inspect
from render import render
import json
m=Model();m.fixed+=optional_parts()
s=stand();print('stand:',len(s.Solids()),s.isValid(),flush=True)
result=inspect(m,[30,60,90,120,150]);(ROOT/'reports/iterations/R2_camera.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
render(m.at(55),ROOT/'images/camera_working.png',scale=76,cam=(150,130,210),target=(0,10,0))
