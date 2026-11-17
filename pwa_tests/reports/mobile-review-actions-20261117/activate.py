from pathlib import Path
import hashlib,json,os,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
B=Path('/web/vmsh_tasks_bot');R=B/'deploy/releases/mobile-review-actions-20261117';S=R/'source';current=B/'vmshpwa/current';target=B/'vmshpwa/releases/mobile-review-actions-20261117'
staged=json.loads((R/'staged.json').read_text());previous=Path(staged['previous'])
assert current.resolve()==previous
sys.path.insert(0,str(S))
from vmshpwa.scripts.static_release import verify_release
verify_release(target.name,'2026-11-17T06:30:00Z',release_root=B/'vmshpwa/releases')
expected=json.loads((R/'ui-hashes.json').read_text())
for name,digest in expected.items():assert hashlib.sha256((S/name).read_bytes()).hexdigest()==digest,name
profile=B/'vmsh_tasks_bot/creds_prod/vmsh_bot_config_prod.json';profile_hash=hashlib.sha256(profile.read_bytes()).hexdigest()
def point(destination):
 temp=current.with_name('current.mobile-review-next');temp.symlink_to(destination);os.replace(temp,current)
def fetch(path):
 with urlopen(Request('https://vmsh.shashkovs.ru'+path,headers={'Cache-Control':'no-cache','Accept-Encoding':'identity'}),timeout=30) as r:
  assert r.status==200
  return r.read()
point(target)
try:
 for app in ('landing','student','family','staff'):
  path='/' if app=='landing' else f'/{app}/'
  assert fetch(path)==(target/app/'index.html').read_bytes(),app
 assets=sorted(p for p in (target/'staff/assets').rglob('*') if p.suffix in ('.js','.css'))
 def check(p):
  assert hashlib.sha256(fetch('/staff/'+p.relative_to(target/'staff').as_posix())).digest()==hashlib.sha256(p.read_bytes()).digest(),p.name
  return p.name
 with ThreadPoolExecutor(max_workers=6) as pool:checked=list(pool.map(check,assets))
 with (R/'http-smoke.log').open('w') as log:
  subprocess.run([str(B/'vmsh_tasks_bot/.venv/bin/python'),str(S/'vmshpwa/scripts/production_http_smoke.py'),'--origin','https://vmsh.shashkovs.ru','--expected-instance','179'],cwd=B/'vmsh_tasks_bot',env={**os.environ,'PYTHONPATH':str(B/'vmsh_tasks_bot')},stdout=log,stderr=subprocess.STDOUT,check=True)
 for unit,state in staged['servicesPreserved'].items():
  assert subprocess.check_output(['systemctl','show',unit,'-p','MainPID','-p','ActiveState'],text=True).strip()==state,unit
 assert hashlib.sha256(profile.read_bytes()).hexdigest()==profile_hash
 assert not list(target.rglob('*.map'))
 assert not (B/'vmshpwa/runtime/service-updating').exists()
 result={**staged,'status':'PASS','sourceCommit':'c6e0e19c8da8c9e965f370bf3dcc26a5af0d7f32','htmlHashesMatched':4,'staffAssetHashesMatched':len(checked),'httpChecksPassed':25,'frontendOnly':True,'servicesRestarted':False,'uiSourceHashes':expected}
 (R/'rollback.txt').unlink(missing_ok=True)
 (R/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
except BaseException:
 point(previous)
 (R/'rollback.txt').write_text('Post-activation verification failed; previous static release restored.\n')
 raise
