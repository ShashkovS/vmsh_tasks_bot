"""Frontend-only release; preserve FirstVDS backend, profile and media patches."""
from pathlib import Path
import hashlib, json, os, shutil, subprocess, sys
from datetime import datetime, timezone
B=Path('/web/vmsh_tasks_bot')
release=sys.argv[1]
R=B/'deploy/releases'/release
S=R/'source'
previous_source=B/'deploy/releases/media-cache-20261107/source'
backend=B/'vmsh_tasks_bot'
current=B/'vmshpwa/current'
previous=current.resolve()
assert previous.name=='firstvds-20261117-media', 'Current release changed; inspect before continuing'
if not S.exists():
 S.mkdir(parents=True)
 shutil.copytree(previous_source/'vmshpwa',S/'vmshpwa',ignore=shutil.ignore_patterns('node_modules','dist','dev-dist','test-results','playwright-report','storybook-static','.cache'))
 subprocess.run(['git','apply','--check',str(R/'ui.patch')],cwd=S,check=True)
 subprocess.run(['git','apply',str(R/'ui.patch')],cwd=S,check=True)
# The FirstVDS media policy is part of the captured source, outside this UI patch.
media='vmshpwa/packages/offline/src/recent-media-policy.ts'
assert (S/media).read_bytes()==(previous_source/media).read_bytes()
profiles=[backend/'creds_prod/vmsh_bot_config_prod.json',B/'cutover-20261117/inputs/production-profile.json']
profile=next(p for p in profiles if p.exists())
profile_hash=hashlib.sha256(profile.read_bytes()).hexdigest()
(S/'creds_prod').mkdir(exist_ok=True);shutil.copyfile(profile,S/'creds_prod/vmsh_bot_config_prod.json');(S/'creds_prod/vmsh_bot_config_prod.json').chmod(0o600)
for root in (backend,previous_source):
 portal=root/'.runtime/glitchtip-portal.json'
 if portal.exists():
  (S/'.runtime').mkdir(exist_ok=True);shutil.copyfile(portal,S/'.runtime/glitchtip-portal.json');(S/'.runtime/glitchtip-portal.json').chmod(0o600);break
units=['vmshpwa.service','gunicorn.vmsh_tasks_bot.service','vmsh-rehearsal-nats.service','vmsh-analytics.timer']
def services():
 return {u:subprocess.check_output(['systemctl','show',u,'-p','MainPID','-p','ActiveState'],text=True).strip() for u in units}
before=services()
for item in S.rglob('*'):shutil.chown(item,user='vmsh_tasks_bot',group='web',follow_symlinks=False)
shutil.chown(S,user='vmsh_tasks_bot',group='web')
# Ensure the service user can traverse the staging tree.
R.chmod(0o755);S.chmod(0o755)
env={**os.environ,'CI':'true','PATH':str(B/'toolchains/node/bin')+':/usr/bin:/bin','npm_config_store_dir':str(B/'cache/pnpm-store'),'npm_config_workspace_concurrency':'1'}
def run(command,log):
 with (R/log).open('wb') as output:
  subprocess.run(['/usr/sbin/runuser','-u','vmsh_tasks_bot','--',*command],cwd=S/'vmshpwa',env=env,stdout=output,stderr=subprocess.STDOUT,check=True)
run(['pnpm','install','--frozen-lockfile'],'dependencies.log')
print('Dependencies ready; building production frontend',flush=True)
run(['/usr/bin/python3',str(S/'vmshpwa/scripts/production_frontend_build.py'),'--release',release,'--media-origin','https://vmsh.shashkovs.ru'],'build.log')
sys.path.insert(0,str(S))
from vmshpwa.scripts.static_release import package_release,verify_release,retain_release_assets
stamp=datetime.now(timezone.utc).isoformat()
manifest=package_release(release,stamp,release_root=B/'vmshpwa/releases')
verify_release(release,stamp,release_root=B/'vmshpwa/releases')
target=B/'vmshpwa/releases'/release
retain_release_assets(previous,B/'vmshpwa');retain_release_assets(target,B/'vmshpwa')
assert profile_hash==hashlib.sha256(profile.read_bytes()).hexdigest()
assert services()==before
assert current.resolve()==previous
(R/'staged.json').write_text(json.dumps({'release':release,'previous':str(previous),'mediaPolicySha256':hashlib.sha256((S/media).read_bytes()).hexdigest(),'configPreserved':True,'servicesPreserved':before,'build':manifest['build']},indent=2)+'\n')
print('STAGED: production build and immutable package verified; not activated',flush=True)
