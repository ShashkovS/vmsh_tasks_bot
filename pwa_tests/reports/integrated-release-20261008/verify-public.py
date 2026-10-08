"""Public bytes/provenance/CSP proof; integrated-release-20261008.md."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


directory = Path(__file__).resolve().parent


def fetch(url):
    with urlopen(Request(url, headers={'Cache-Control': 'no-cache', 'Accept-Encoding': 'identity'}),
                 timeout=30) as response:
        assert response.status == 200
        return response.read(), dict(response.headers)


def verify(mode, origin):
    proof = json.loads((directory / f'production-{mode}.json').read_text())
    release = proof['frontend_release']
    _, headers = fetch(f'{origin}/student/?release={release}')
    csp = next(value for name, value in headers.items() if name.lower() == 'content-security-policy')
    expected_media = proof['builds']['student']['publicMediaOrigin']
    assert expected_media in csp
    if mode == 'vmsh':
        assert 'https://d3ca76cf4cf5-images-bucket.s3.ru1.storage.beget.cloud' in csp
    for audience, build in proof['builds'].items():
        body, _ = fetch(f'{origin}/{audience}/build-provenance.json?release={release}')
        assert json.loads(body) == build
    assets = []
    for asset in proof['public_assets']:
        body, _ = fetch(origin + asset['path'])
        assert hashlib.sha256(body).hexdigest() == asset['sha256']
        assets.append({'path': asset['path'], 'sha256': asset['sha256'], 'bytes_match': True})
    return {'origin': origin, 'source_revision': proof['source_revision'], 'frontend_release': release,
            'public_provenance_matches': True, 'csp_expected_media_origin': True,
            'old_vmsh_origin_retained': mode == 'vmsh', 'assets': assets}


with ThreadPoolExecutor(max_workers=2) as pool:
    result = list(pool.map(lambda pair: verify(*pair),
                          [('vmsh', 'https://vmsh.shashkovs.ru'), ('tlf', 'https://prep.leaders.tech')]))
(directory / 'public-release.json').write_text(json.dumps(
    {'recorded_at': datetime.now(timezone.utc).isoformat(), 'productions': result}, indent=2) + '\n')
print('PASS: both public origins serve exact release bytes/provenance and expected media CSP.')
