from design import *
from assembly_reader import bounds
from render import render
import time,itertools,json

def overlap_bbox(a,b,tol=.00001):return all(min(a[i+3],b[i+3])-max(a[i],b[i])>tol for i in range(3))
def exception(a,b):
    return ('XL430_W250' in [a.name,b.name] and (a.role=='servo_body_tap' or b.role=='servo_body_tap'))

def inspect(m,angles):
    results=[];done=set();n=0;clearances=[]
    for ang in angles:
        rows=m.at(ang);bbs=[bounds(r.shape) for r in rows]
        for i,j in itertools.combinations(range(len(rows)),2):
            a,b=rows[i],rows[j]; key=(a.name,b.name)
            if a.group==b.group or (a.group in ['fixed','supplier'] and b.group in ['fixed','supplier']):
                if key in done:continue
                done.add(key)
            if not overlap_bbox(bbs[i],bbs[j]):continue
            if exception(a,b):continue
            try:
                v=a.shape.intersect(b.shape).Volume();n+=1
            except Exception as e:
                results.append({'angle':ang,'a':a.name,'b':b.name,'error':repr(e)});continue
            if v>1e-4:results.append({'angle':ang,'a':a.name,'b':b.name,'volume':round(v,6)})
        qm={q.name:q.shape for q in rows}
        if all(name in qm for name in ['jaw_1','frame','retainer_top','retainer_bottom']):
            vals={name:qm['jaw_1'].distance(qm[name]) for name in ['frame','retainer_top','retainer_bottom']}
            clearances.append({'angle':ang,'minimums_mm':vals,'pass':min(vals.values())>.1499})
        print('angle',ang,'hits',len(results),'booleans',n,flush=True)
    return dict(revision=m.p.revision,angles=angles,collisions=results,boolean_tests=n,guide_clearances=clearances,clearance_pass=all(x['pass'] for x in clearances))
if __name__=='__main__':
    m=Model();s=time.monotonic()
    render(m.at(75),ROOT/'images/iteration_R1_iso.png',scale=68)
    render(m.at(75),ROOT/'images/iteration_R1_front.png',cam=(0,0,250),target=(0,0,0),scale=60)
    render(m.at(75),ROOT/'images/iteration_R1_side.png',cam=(250,0,0),target=(0,0,0),scale=60)
    result=inspect(m,list(range(30,151,15)));result['seconds']=time.monotonic()-s
    (ROOT/'reports/iterations/R1.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
