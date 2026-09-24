import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from pathlib import Path
from assembly_reader import bounds
p=Path('/mnt/data/PG2_XL430/reference/000_DC11_A01_DUMMY_1.step')
s=cq.importers.importStep(str(p)).val()
print('solid',len(s.Solids()),s.isValid())
for i,f in enumerate(s.Faces()):
 if f.geomType()=='CYLINDER':
  cy=BRepAdaptor_Surface(f.wrapped).Cylinder();p=cy.Location();a=cy.Axis().Direction()
  print(i,'r',round(cy.Radius(),3),'axis',tuple(round(v,3) for v in [p.X(),p.Y(),p.Z()]),tuple(round(v,3) for v in [a.X(),a.Y(),a.Z()]),'bnd',tuple(round(v,3) for v in bounds(f)))
