"""C9 corrective-action check near the C8 closest-approach failure."""
from __future__ import annotations
import json, hashlib, math
import numpy as np
import jaw_revision as j
from jaw_revision import base, ROOT
from pose import pose

if __name__=='__main__':
    ref=j.assembled(90,d=j.parts()); rows=[]
    for angle in np.linspace(95,125,301):
        its={i.name:i for i in pose(ref,float(angle))}
        for lr in ['R','L']:
            gap=float(its['carriage_'+lr].shape.distance(its['crank'].shape))
            if not math.isfinite(gap):raise ValueError('invalid distance')
            rows.append({'angle_deg':float(angle),'side':lr,'distance_mm':gap})
    minimum=min(rows,key=lambda r:r['distance_mm'])
    out={'revision':j.REVISION,'source_sha256':hashlib.sha256((ROOT/'source/jaw_revision.py').read_bytes()).hexdigest(),
         'pass':minimum['distance_mm']>=.29999,'sampled_angles':301,'step_deg':.1,'interval_deg':[95,125],
         'minimum':minimum,'rows':rows,'scope':'Targeted nominal sampled distance; not continuous proof.'}
    (ROOT/'reports/refined_clearance.json').write_text(json.dumps(out,indent=2))
    print(minimum,flush=True)
    if not out['pass']:raise SystemExit(2)
