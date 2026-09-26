from onshape_api import *
import shutil
asm=api(f'/assemblies/d/{DID}/w/{WID}/e/{ASM}',query={'includeMateConnectors':'true','includeMateFeatures':'true','includeNonSolids':'true'})
save('assembly-final.json',asm)
f=api(f'/assemblies/d/{DID}/w/{WID}/e/{ASM}/features')
save('features-final.json',f)
print('feature states',[(k,v.get('featureStatus')) for k,v in f['featureStates'].items()])
version=api(f'/documents/d/{DID}/versions','POST',{'documentId':DID,'workspaceId':WID,'name':'V2 independent rebuild - motion and interference verified'})
(OUTPUT/'kinematic-version.json').write_text(json.dumps(version,indent=2))
out=OUTPUT/'robot';out.mkdir(exist_ok=True)
config=json.loads((PRIVATE_ROOT.parent/'outputs/robot/config.json').read_text())
config['url']=f'https://cad.onshape.com/documents/{DID}/v/{version["id"]}/e/{ASM}'
(out/'config.json').write_text(json.dumps(config,indent=2))
doc=api(f'/documents/{DID}');print('public',doc.get('isPublic'), 'version',version['id'])
translations=api(f'/translations/d/{DID}')
save('translations-final.json',translations)
print('translations',[t['requestState'] for t in translations['items']])
