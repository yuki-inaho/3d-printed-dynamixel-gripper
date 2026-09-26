"""Serialize browser pose export and independent local STEP intake."""
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'outputs/low-profile-250g'
targets=json.loads((OUT/'reports/native-pose-targets.json').read_text())['cases']
for target in targets:
    name=target['name']
    step=OUT/'CAD/native-poses'/f'{name}.step'
    report=OUT/'reports'/f'native-step-{name}.json'
    if not step.exists():
        print('EXPORT',name,flush=True)
        subprocess.run([sys.executable,str(HERE/'export_one.py'),name],cwd=ROOT,check=True,timeout=900)
    if not report.exists():
        subprocess.run([sys.executable,str(HERE/'analyze_ui_step.py'),str(step),'--output',str(report)],cwd=ROOT,check=True,timeout=300)
    info=json.loads(report.read_text())
    assert info['occurrences']==262 and info['solid_count']==207
    assert any('MILLI' in unit for unit in info['step_si_units'])
    print('READABLE STEP',name,info['sha256'],flush=True)
print('ALL 11 UI STEPs readable; full URDF/FK comparison follows',flush=True)
