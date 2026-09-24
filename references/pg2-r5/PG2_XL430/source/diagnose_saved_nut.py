from design import *
from assembly_reader import read_step,bounds
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN,TopAbs_OUT
import json
_,_,rows=read_step(str(ROOT/'CAD/PG2_open.step'));rs={r.name:r.world for r in rows}
f=rs['frame'];n=rs['rail_nut_64_-38.5'];pts=[]
for x,y,z in [(64,-38.5,2),(66,-38.5,2),(64,-40.5,2),(61.5,-38.5,2),(64,-36,2)]:
    c=BRepClass3d_SolidClassifier(f.Solids()[0].wrapped,gp_Pnt(x,y,z),1e-7)
    pts.append({'xyz':[x,y,z],'frame_classification':str(c.State())})
r={'frame_valid':f.isValid(),'nut_valid':n.isValid(),'nut_bounds':bounds(n),'nut_volume':n.Volume(),'common_volume':f.intersect(n).Volume(),'points':pts}
(ROOT/'reports/iterations/R3_saved_nut_diagnosis.json').write_text(json.dumps(r,indent=2));print(r)
