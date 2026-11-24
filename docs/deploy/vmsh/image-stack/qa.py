"""Actual application conversion on public HEIC regression samples, no S3/DB writes."""
import asyncio,hashlib,importlib.util,json,os,subprocess,sys,time,types
from pathlib import Path
B=Path('/web/vmsh_tasks_bot');R=B/'image-stack';Q=R/'qa'
sys.path.insert(0,str(B/'vmsh_tasks_bot'))
# Load pure converter/scanner modules without content/__init__ importing models
# and production configuration. This is isolated QA wiring, never app auth.
package=types.ModuleType('helpers.pwa.content')
package.__path__=[str(B/'vmsh_tasks_bot/helpers/pwa/content')]
sys.modules['helpers.pwa.content']=package
name='helpers.pwa.content._image_stack_candidate'
spec=importlib.util.spec_from_file_location(name,R/'assets-candidate.py');m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
MAGICK='/opt/vmsh-image-stack/20261117/bin/magick'
async def main():
 converter=m.ContentAssetConverter(m.ContentAssetTools('unused','unused',MAGICK,'must-not-run-cwebp'),temp_root=Q,timeout_seconds=45)
 results=[]
 for source in sorted((Q/'inputs').iterdir()):
  if source.suffix.lower() not in ['.heic','.heif','.avif','.png','.jpg','.webp']:continue
  payload=source.read_bytes();start=time.monotonic()
  output=await converter.raster_to_webp(payload)
  path=Q/(source.name+'.webp');path.write_bytes(output.data)
  assert output.media_type=='image/webp' and max(output.width,output.height)<=1920
  # Independent system WebP decoder validates the new encoder output.
  subprocess.run(['dwebp',str(path),'-o','/dev/null'],check=True,capture_output=True,timeout=20)
  identify=subprocess.check_output([MAGICK,'identify','-format','%[profiles]|%c',str(path)],text=True).strip()
  assert identify=='|',identify
  try:
   old=subprocess.run(['/usr/bin/magick',str(source)+'[0]','-auto-orient','-strip','-resize','1920x1920>','-quality','82',str(Q/'old.webp')],capture_output=True,timeout=30)
   old_ok=old.returncode==0
  except subprocess.TimeoutExpired:old_ok=False
  results.append({'sample':source.name,'sourceSha256':hashlib.sha256(payload).hexdigest(),'width':output.width,'height':output.height,'outputBytes':len(output.data),'directWebp':True,'oldSystemSucceeded':old_ok,'elapsedMs':round((time.monotonic()-start)*1000)})
  print(json.dumps(results[-1]),flush=True)
 try:await converter.raster_to_webp(b'invalid image')
 except m.AssetConversionError:pass
 else:raise AssertionError('Corrupt input accepted')
 proof={'candidateSha256':hashlib.sha256((R/'assets-candidate.py').read_bytes()).hexdigest(),'samples':results,'corruptRejected':True,'externalCwebpUsed':False}
 (Q/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
asyncio.run(main())
