from pathlib import Path
import shutil,json
root=Path(__file__).resolve().parent;out=root.parent/'outputs';dest=out/'reproduce';dest.mkdir(exist_ok=True)
for name in ['build_composites.py','setup_assembly.py','make_connectors.py','build_joints.py','joint_definitions.py','set_pose.py']:
    shutil.copy2(root/name,dest/name)
api=(root/'onshape_api.py').read_text()
a=api.index('PRIVATE_ROOT=');b=api.index('\ndef api(',a)
api=api[:a]+'''ROOT=Path(os.environ['ONSHAPE_TASK_WORK']).resolve()
OUTPUT=Path(os.environ['ONSHAPE_TASK_OUTPUT']).resolve()
ROOT.mkdir(parents=True,exist_ok=True);OUTPUT.mkdir(parents=True,exist_ok=True)
_project=json.loads((ROOT/'project.json').read_text())
DID,WID,PS,ASM=(_project[k] for k in ('did','wid','ps','asm'))
if (ROOT/'bound-project.json').exists():
    assert json.loads((ROOT/'bound-project.json').read_text())==_project,'State directory belongs to a different document'
else:
    (ROOT/'bound-project.json').write_text(json.dumps(_project,indent=2))
'''+api[b:]
api=api.replace("credentials=json.loads((PRIVATE_ROOT/'onshape-key-private.json').read_text())['data']","credentials={'accessKey':os.environ['ONSHAPE_ACCESS_KEY'],'secretKey':os.environ['ONSHAPE_SECRET_KEY']}")
api=api.replace("counter=PRIVATE_ROOT/'api-count.txt'","counter=ROOT/'api-count.txt'")
(dest/'onshape_api.py').write_text(api)
(dest/'project.example.json').write_text(json.dumps({'did':'NEW_DOCUMENT_ID','wid':'NEW_WORKSPACE_ID','ps':'IMPORTED_262_BODY_PARTSTUDIO_ID','asm':'EMPTY_ASSEMBLY_ID'},indent=2))
shutil.copytree(out/'robot/licenses',out/'rebuild/robot/licenses',dirs_exist_ok=True)
shutil.copy2(out/'robot/NOTICE.md',out/'rebuild/robot/NOTICE.md')
shutil.copytree(Path('/home/inaho-omen/.codex/skills/onshape-robot-workflow'),out/'onshape-robot-workflow',dirs_exist_ok=True)
print('Reproduction scripts and skill copied; no credentials copied.')
