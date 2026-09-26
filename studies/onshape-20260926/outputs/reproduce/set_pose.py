import sys,math
from onshape_api import *
angle=float(sys.argv[1]); label=sys.argv[2] if len(sys.argv)>2 else str(angle)
mates=json.loads((ROOT/'mates.json').read_text())
fid=mates['dof_gripper_drive']['feature']['featureId']
p=f'/assemblies/d/{DID}/w/{WID}/e/{ASM}'
targets=[{'jsonType':'Revolute','featureId':fid,'rotationZ':math.radians(90-angle),'ownerOccurrencePath':[]}]
for name in ['joint1_yaw','joint2_shoulder','joint3_elbow','joint4_wrist']:
    targets.append({'jsonType':'Revolute','featureId':mates['dof_'+name]['feature']['featureId'],'rotationZ':0.,'ownerOccurrencePath':[]})
r=api(p+'/matevalues','POST',{'mateValues':targets})
save(f'pose-{label}-matevalues.json',r)
save(f'pose-{label}.json',api(p,query={'includeMateConnectors':'true','includeMateFeatures':'true','includeNonSolids':'true'}))
print(label,[(v.get('mateName'),v.get('rotationZ',v.get('translationZ'))) for v in r['mateValues'] if v.get('jsonType') in ('Revolute','Slider')])
