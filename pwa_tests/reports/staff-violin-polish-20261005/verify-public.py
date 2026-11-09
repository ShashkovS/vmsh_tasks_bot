"""Verify public provenance and exact deployed graph chunk bytes without auth."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

report_dir = Path(__file__).resolve().parent

def verify(mode, origin):
    production = json.loads((report_dir / f'production-{mode}.json').read_text())
    bundle = json.loads((report_dir / f'bundle-{mode}.json').read_text())
    release = production['frontend_release']
    assert release == bundle['frontend_release']
    builds = {}
    for audience in ('landing', 'student', 'family', 'staff'):
        prefix = f'/{audience}'
        request = Request(f'{origin}{prefix}/build-provenance.json?release={release}',
                          headers={'Cache-Control': 'no-cache'})
        with urlopen(request, timeout=20) as response:
            public = json.load(response)
        assert public == production['builds'][audience]
        builds[audience] = public['releaseId']
    assets = []
    for chunk in bundle['graph_chunks']:
        request = Request(origin + chunk['path'], headers={'Accept-Encoding': 'identity'})
        with urlopen(request, timeout=20) as response:
            digest = hashlib.sha256(response.read()).hexdigest()
            content_type = response.headers.get('Content-Type')
        assert digest == chunk['sha256']
        assets.append(dict(path=chunk['path'],sha256=digest,content_type=content_type,bytes_match=True))
    return dict(origin=origin,frontend_release=release,public_provenance=builds,graph_assets=assets)

with ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(lambda pair: verify(*pair),
                           [('vmsh','https://vmsh.shashkovs.ru'),
                            ('tlf','https://prep.leaders.tech')]))
(report_dir / 'public-release.json').write_text(json.dumps(results,indent=2)+'\n')
print('PASS: both public origins serve the expected production provenance and exact new graph chunks.')
