"""Create/apply UI named positions serially, preserving every CLI result."""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'outputs/low-profile-250g'
targets = json.loads((OUT / 'reports/native-pose-targets.json').read_text())['cases']
template = (HERE / 'named-pose.template.js').read_text()
report_path = OUT / 'reports/native-ui-poses.json'
report = json.loads(report_path.read_text()) if report_path.exists() else {
    'status': 'RUNNING', 'direct_api_calls': 0,
    'method': 'Normal UI Named positions, stored values and applied notification',
    'numerical_geometry_verification': 'pending UI STEP export',
    'cases': [
        {'name': 'zero', 'stored_deg': [0, 0, 0, 0, 0], 'applied_message': True,
         'evidence': 'interactive CLI zero is applied notification and onshape-pose-zero.png'},
        {'name': 'small_joint1_yaw', 'rowId': '0z/QhXG1E9KW7uLo', 'stored_deg': [10, 0, 0, 0, 0],
         'applied_message': True, 'evidence': 'interactive pilot result and onshape-pose-small_joint1_yaw.png'},
    ],
}
logs = HERE / 'ui-logs'
logs.mkdir(exist_ok=True)
for row in targets:
    name = row['name']
    if name in {r['name'] for r in report['cases']}:
        continue
    values = list(row['expected_deg'].values())
    nonzero = [i for i, v in enumerate(values) if v]
    assert len(nonzero) <= 1
    col = nonzero[0] if nonzero else None
    spec = {'name': name, 'col': col, 'deg': values[col] if col is not None else 0, 'reuse': name}
    script = HERE / 'current-pose.js'
    script.write_text(template.replace('__CASE__', json.dumps(spec)))
    print('START', name, flush=True)
    proc = subprocess.run(['rtk', 'proxy', 'npx', '--yes', '@playwright/cli', '-s=onshape-headless',
                           'run-code', '--filename=low-profile/current-pose.js'],
                          cwd=ROOT/'work', capture_output=True, text=True, timeout=300)
    raw = proc.stdout + proc.stderr
    log_path = logs / f'{name}.txt'
    if log_path.exists():
        i = 1
        while (logs / f'{name}-attempt-{i}.txt').exists():
            i += 1
        log_path.rename(logs / f'{name}-attempt-{i}.txt')
    log_path.write_text(raw)
    try:
        if proc.returncode or '### Error' in raw:
            raise RuntimeError(raw[-3500:])
        data = json.loads(raw.split('### Result\n', 1)[1].split('\n###', 1)[0].strip())
        assert data['name'] == name and data['stored_deg'] == values and data['applied_message']
    except Exception as exc:
        report.update(status='FAILED', failed_case=name, error=str(exc))
        report_path.write_text(json.dumps(report, indent=2)+'\n')
        raise
    report['cases'].append(data)
    if report.get('failed_case') == name:
        report.setdefault('failure_history', []).append({'case':report.pop('failed_case'),'error':report.pop('error'),'resolution':'UI retry; see timestamped WORKDOC and captured values'})
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print('PASS UI APPLY', name, data['stored_deg'], flush=True)
report['status'] = 'UI_APPLIED_NUMERICAL_CHECK_PENDING'
report_path.write_text(json.dumps(report, indent=2)+'\n')
print('ALL', len(report['cases']), 'UI positions applied; STEP numerical verification pending', flush=True)
