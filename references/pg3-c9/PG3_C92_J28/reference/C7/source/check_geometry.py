"""Independent geometric predicates. Exceptions and invalid results fail closed."""
import math
from itertools import combinations
import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from design import bounds,cyl

def bbox_overlap(a,b,tol=1e-7):
    return all(min(a[k+3],b[k+3])-max(a[k],b[k])>tol for k in range(3))
def common(a,b):
    op=BRepAlgoAPI_Common(a.wrapped,b.wrapped);op.Build()
    if not op.IsDone() or op.Shape().IsNull():raise RuntimeError('boolean not done/null')
    s=cq.Shape.cast(op.Shape())
    v=sum(max(0.,ss.Volume()) for ss in s.Solids())
    if not math.isfinite(v) or not s.isValid():raise RuntimeError('bad intersection result')
    # Some OCCT coincident, twice-transformed B-reps return an empty common.
    # A matching bounding box and volume is a suspicion trigger, NOT a proof to bless.
    if v < 1e-12 and all(abs(x-y)<1e-7 for x,y in zip(bounds(a),bounds(b))) and abs(a.Volume()-b.Volume())<1e-6 and a.Volume()>.01:
        raise RuntimeError('empty common for coincident-envelope equal-volume bodies; inspect independently')
    return s,v

def collision_check(items,tol=.01,rigid_cache=None):
    failures=[];allowed=[];checks=0;bs=[bounds(it.shape) for it in items]
    for i,j in combinations(range(len(items)),2):
        if not bbox_overlap(bs[i],bs[j]):continue
        a,b=items[i],items[j]
        key=tuple(sorted([a.name,b.name]))
        if rigid_cache is not None and a.group==b.group and key in rigid_cache:continue
        s,v=common(a.shape,b.shape);checks+=1
        if rigid_cache is not None and a.group==b.group:rigid_cache.add(key)
        if v<=tol:continue
        ns={a.name,b.name}
        # Only the pilot annulus engaged by an explicitly named self-tapper.
        if 'XL430_fixed' in ns and any(n.startswith('case_tapper_') for n in ns):
            nm=next(n for n in ns if n.startswith('case_tapper_'));x=float(nm.rsplit('_',1)[1])
            region=cyl(1.31,2.66,(x,-8,14.34));res=s.cut(region)
            rem=sum(max(0.,ss.Volume()) for ss in res.Solids())
            if rem<=tol:
                allowed.append({'pair':[a.name,b.name],'volume':v,'zone':'case pilot at x+/-11, y=-8, z14.34..17.0'});continue
        failures.append({'a':a.name,'b':b.name,'volume_mm3':v})
    return {'failures':failures,'allowed_threads':allowed,'boolean_checks':checks}
if __name__=='__main__':
    from design import *
    import json
    d=parts();reports=[];cache=set()
    for a in [25,45,70,90,110,125,135]:
        its=assembled(a,d=d);r=collision_check(its,rigid_cache=cache);r['angle']=a;reports.append(r);print(a,r['failures'],flush=True)
    (ROOT/'reports/iterations/latest_sanity.json').write_text(json.dumps(reports,indent=2))
