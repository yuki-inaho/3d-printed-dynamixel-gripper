from pathlib import Path
import json,zipfile,shutil,hashlib
root=Path(__file__).resolve().parent;out=root.parent/'outputs'
# Retain only model/version identifiers needed to reproduce the result.
for p in [out/'onshape-reference-version.json',out/'onshape-kinematic-version.json',out/'rebuild/reference-version.json',out/'rebuild/kinematic-version.json']:
    d=json.loads(p.read_text());(root/('original-'+p.parent.name+'-'+p.name)).write_text(json.dumps(d,indent=2))
    p.write_text(json.dumps({k:v for k,v in d.items() if k in ['id','name','documentId','workspaceId','createdAt','microversion','description']},indent=2))
config=json.loads((out/'robot/config.json').read_text())
config['url']='https://cad.onshape.com/documents/1f8f316ef4f488303d1c1902/v/9d614fea1354d083cde3bf56/e/282c9739d5fb8e5aa9a89f3f'
(out/'robot/config.json').write_text(json.dumps(config,indent=2))
# Source notices travel with each robot model.
for dest in [out/'robot',out/'rebuild/robot']:
    shutil.copy2(out/'source-manifest.json',dest/'source-manifest.json')
    (dest/'README.md').write_text('Kinematic Onshape export. See the top-level README.md and VALIDATION_GUIDE.md in the full bundle.\nUse robot.urdf with assets/. robot.onshape-raw.urdf is the preserved raw exporter result.\nRun pg3_states.py to obtain nonlinear closed-loop joint states; run validate_robot.py with numpy/trimesh.\nMass, inertia, hardware home and effort/velocity are unmeasured. No dynamics/control acceptance.\n')
key=json.loads((root/'onshape-key-private.json').read_text())['data']
files=[p for p in out.rglob('*') if p.is_file() and p.suffix not in ['.zip','.pyc'] and '__pycache__' not in p.parts and p.name!='delivery-check.json']
for p in files:
    blob=p.read_bytes()
    for field in ['accessKey','secretKey']:
        assert key[field].encode() not in blob, 'Credential detected in '+str(p.relative_to(out))
    assert 'private' not in p.name.lower(),p
bundle=out/'onshape-robot-bundle.zip'
with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:z.write(p,p.relative_to(out))
with zipfile.ZipFile(bundle) as z:assert z.testzip() is None
report={'file':bundle.name,'sha256':hashlib.sha256(bundle.read_bytes()).hexdigest(),'bytes':bundle.stat().st_size,'files':len(files),'known_credentials_scan':'PASS','archive_integrity':'PASS'}
(out/'delivery-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
