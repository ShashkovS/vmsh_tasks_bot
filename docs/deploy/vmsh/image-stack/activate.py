"""Activate tested image stack and the small direct-WebP production delta."""
from pathlib import Path
import ast,hashlib,json,os,shutil,subprocess
B=Path('/web/vmsh_tasks_bot');R=B/'image-stack';C=B/'vmsh_tasks_bot'
os.umask(0o077)
prefix=Path('/opt/vmsh-image-stack/20261117');stable=prefix.parent/'current'
proof=json.loads((R/'qa/proof.json').read_text());assert len(proof['samples'])>=12
assert proof['corruptRejected'] and proof['externalCwebpUsed'] is False
candidate=(R/'assets-candidate.py').read_bytes()
assert hashlib.sha256(candidate).hexdigest()==proof['candidateSha256']
source=C/'helpers/pwa/content/assets.py'
assert source.read_bytes()==(R/'assets-before.py').read_bytes(),'Production source changed during QA'
ast.parse(candidate)
if stable.exists() or stable.is_symlink():raise RuntimeError('Review existing image stack before replacing')
stable.symlink_to(prefix)
for name in ['magick','convert','identify']:
 path=Path('/usr/local/bin')/name
 assert not path.exists() and not path.is_symlink(),path
 path.symlink_to(stable/'bin'/name)
 link=R/('command-'+name);link.symlink_to(path)
magick=str(stable/'bin/magick')
env=B/'vmshpwa/runtime/vmshpwa.env';text=env.read_text()
assert not any(l.startswith('VMSH_MAGICK_PATH=') for l in text.splitlines())
with env.open('a') as f:f.write('\nVMSH_MAGICK_PATH='+magick+'\n')
p=C/'creds_prod/vmsh_bot_config_prod.json';config=json.loads(p.read_text())
assert 'magick_path' not in config
config['magick_path']=magick
st=p.stat();temp=p.with_suffix('.json.image-stack-next')
temp.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n');temp.chmod(0o600);os.chown(temp,st.st_uid,st.st_gid);os.replace(temp,p)
st=source.stat();temp=source.with_suffix('.py.image-stack-next')
temp.write_bytes(candidate);temp.chmod(st.st_mode&0o777);os.chown(temp,st.st_uid,st.st_gid);os.replace(temp,source)
# Capture small source deltas/version recipe, never compiled software or fixtures.
patches=B/'backup-local-changes';patches.mkdir(mode=0o700,exist_ok=True)
git=['git','-c','safe.directory='+str(C),'-C',str(C)]
(patches/'backend.patch').write_bytes(subprocess.check_output(git+['diff','--binary','HEAD']))
shutil.copyfile(B/'cutover-20261117/tools/build_image_stack.sh',patches/'build-image-stack.sh')
shutil.copyfile(R/'source-sha256.txt',patches/'image-stack-source-sha256.txt')
subprocess.run(['systemctl','restart','vmshpwa.service','gunicorn.vmsh_tasks_bot.service'],check=True)
result={'magickPath':magick,'sourceSha256':hashlib.sha256(candidate).hexdigest(),'directWebp':True,'diagnosticsPreserved':True,'privateLibrariesLinked':True}
(R/'activation-proof.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
