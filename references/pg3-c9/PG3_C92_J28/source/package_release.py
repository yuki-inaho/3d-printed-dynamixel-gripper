"""Package exact files after current-report validation; verify ZIP bytes against hashes."""
from pathlib import Path
import hashlib, json, zipfile
import jaw_revision as j
from jaw_revision import ROOT
from finish_release import main as finish

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    finish()
    eligible=lambda p:p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.pid'] and p.name not in ['SHA256SUMS.txt']
    paths=sorted(p for p in ROOT.rglob('*') if eligible(p))
    sums={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths}
    (ROOT/'SHA256SUMS.txt').write_text(''.join(f'{v}  {k}\n' for k,v in sums.items()))
    paths.append(ROOT/'SHA256SUMS.txt')
    dest=ROOT.parent/'PG3_C92_J28_C9.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in paths:archive.write(p,ROOT.name+'/'+str(p.relative_to(ROOT)))
    with zipfile.ZipFile(dest) as archive:
        corrupt=archive.testzip()
        if corrupt:raise RuntimeError('Bad archive member '+corrupt)
        for k,expected in sums.items():
            if sha(archive.read(ROOT.name+'/'+k))!=expected:raise RuntimeError('Archive hash mismatch '+k)
    result={'revision':j.REVISION,'pass':True,'zip':str(dest),'bytes':dest.stat().st_size,'sha256':sha(dest.read_bytes()),'verified_members':len(sums)}
    (ROOT.parent/'PG3_C92_J28_C9_archive_check.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
