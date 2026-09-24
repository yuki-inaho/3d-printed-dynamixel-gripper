from design import *
from review_iteration import inspect
from render import render
import time,json
m=Model();s=time.monotonic()
render(m.at(55),ROOT/'images/R2_iso.png',scale=67)
result=inspect(m,list(range(30,151,10)));result['seconds']=time.monotonic()-s
(ROOT/'reports/iterations/R2.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
