from design import *
from review_iteration import overlap_bbox
from assembly_reader import bounds
import json
m=Model();f=ROOT/'CAD/parts/01_frame.step';cq.exporters.export(m.printed['01_frame'],str(f));s=cq.importers.importStep(str(f)).val();results=[]
for p in m.at(30):
 if p.name.startswith(('rail_nut','mount_bolt','rail_bolt')) or p.name=='motor_mount':
  # Round-trip the counterpart too, since the original issue involved the serialized pair.
  tmp=ROOT/'reports/iterations/_counterpart.step';cq.exporters.export(p.shape,str(tmp));t=cq.importers.importStep(str(tmp)).val()
  if overlap_bbox(bounds(s),bounds(t)):
   v=s.intersect(t).Volume();results.append({'other':p.name,'volume':v,'pass':v<1e-4})
r={'pass':all(x['pass'] for x in results),'revision':P.revision,'pairs':results};(ROOT/'reports/frame_roundtrip_regression.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2));assert r['pass']
