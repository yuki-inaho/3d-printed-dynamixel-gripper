"""Rebuild the J28 variant, stopping on every failed stage. No hardware control."""
from pathlib import Path
import os, subprocess, sys
HERE=Path(__file__).resolve().parent

def main():
    env=os.environ.copy();env['OMP_NUM_THREADS']='1';env['OPENBLAS_NUM_THREADS']='1'
    for stage in ['audit','sanity','sweep','assembly','export','saved']:
        subprocess.run([sys.executable,str(HERE/'audit_and_export.py'),'--stage',stage],check=True,env=env)
    for name in ['check_refined_clearance.py','make_visuals.py','finish_release.py']:
        subprocess.run([sys.executable,str(HERE/name)],check=True,env=env)

if __name__=='__main__':main()
