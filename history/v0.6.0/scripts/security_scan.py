#!/usr/bin/env python3
import pathlib,re,sys
root=pathlib.Path(__file__).resolve().parents[1]; bad=[]
patterns=[re.compile(r'AKIA[0-9A-Z]{16}'),re.compile(r'-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----'),re.compile(r'(?i)(api[_-]?key|secret|token)\s*[:=]\s*["\'][^"\']{12,}["\']')]
for p in root.rglob('*'):
    if not p.is_file() or any(x in p.parts for x in ('.git','__pycache__','data','backups')): continue
    try: text=p.read_text(errors='ignore')
    except Exception: continue
    if '.env.example' in str(p): continue
    for n,pat in enumerate(patterns,1):
        if pat.search(text): bad.append(f'{p}:{n}')
print('security_scan findings=',len(bad))
for x in bad: print(x)
sys.exit(1 if bad else 0)
