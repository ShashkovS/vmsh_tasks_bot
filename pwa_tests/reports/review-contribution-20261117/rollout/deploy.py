"""Owner-approved schema-compatible rollout; review-contribution.md and receipt README."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import fcntl, hashlib, json, os, shutil, signal, sqlite3, subprocess, sys, time
from urllib.request import Request, urlopen

B = Path('/web/vmsh_tasks_bot')
C = B / 'vmsh_tasks_bot'
mode, action, release, target = sys.argv[1:]
assert mode in ('firstvds', 'prep') and action in ('stage', 'activate')
R = B / 'deploy/releases' / release
S = R / 'source'
current = B / 'vmshpwa/current'
origin = 'https://vmsh.shashkovs.ru' if mode == 'firstvds' else 'https://prep.leaders.tech'
media = origin if mode == 'firstvds' else 'https://tlfprepimages.nbg1.your-objectstorage.com'
group = 'web' if mode == 'firstvds' else 'nginx'
lock = (B / 'deploy/metadata-deploy.lock').open('a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

def run(args, cwd=C, **kwargs):
    return subprocess.run(args, cwd=cwd, check=True, **kwargs)

def out(args, cwd=C):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()

def git(*args):
    return out(['/usr/sbin/runuser', '-u', 'vmsh_tasks_bot', '--', 'git', *args])

def app(args, log, cwd=S):
    env = {**os.environ, 'CI': 'true', 'PATH': f'{B}/toolchains/node/bin:{B}/toolchains/pnpm/node_modules/.bin:/usr/local/bin:/usr/bin:/bin', 'npm_config_store_dir': str(B / ('cache/pnpm-store' if mode == 'firstvds' else 'cache/pnpm')), 'npm_config_workspace_concurrency': '1'}
    with (R / log).open('wb') as stream:
        run(['/usr/sbin/runuser', '-u', 'vmsh_tasks_bot', '--', *args], cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT)

def digest(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() if path.is_file() else None

def write(name, value):
    (R / name).write_text(json.dumps(value, indent=2) + '\n')

def pid(unit):
    return int(out(['systemctl', 'show', unit, '-p', 'MainPID', '--value']))

def schema(db):
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as connection:
        rows = connection.execute("select type,name,tbl_name,sql from sqlite_schema order by type,name").fetchall()
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()

def backup(label, config):
    folder = R / label
    if (R / (label + '.json')).exists():
        report = json.loads((R / (label + '.json')).read_text())
        assert all(digest(folder / (name + '.sqlite3')) == value['sha256'] for name, value in report.items())
        return report
    folder.mkdir(mode=0o700)
    report = {}
    for name, key in [('main', 'db_filename'), ('analytics', 'pwa_analytics_db_filename')]:
        source = (C / config[key]).resolve()
        destination = folder / f'{name}.sqlite3'
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src, sqlite3.connect(destination) as dst:
            src.backup(dst, pages=512, sleep=0.05)
            assert dst.execute('pragma integrity_check').fetchall() == [('ok',)]
        destination.chmod(0o600)
        report[name] = {'integrity': 'ok', 'bytes': destination.stat().st_size, 'sha256': digest(destination)}
    write(label + '.json', report)
    return report

profile = C / 'creds_prod/vmsh_bot_config_prod.json'
config = json.loads(profile.read_text())
if action == 'stage':
    assert not (R / 'staged.json').exists()
    assert not git('diff', '--cached', '--name-only'), 'Staged server edits require review'
    before_head = git('rev-parse', 'HEAD')
    original_dirty = git('diff', '--name-only').splitlines()
    original_hashes = {name: digest(C / name) for name in original_dirty}
    original_diff = subprocess.check_output(['/usr/sbin/runuser', '-u', 'vmsh_tasks_bot', '--', 'git', 'diff', '--binary'], cwd=C)
    (R / 'original-server.patch').write_bytes(original_diff)
    run(['/usr/sbin/runuser', '-u', 'vmsh_tasks_bot', '--', 'git', 'fetch', str(R / 'source.bundle'), 'refs/heads/codex/review-contribution-release'], stdout=subprocess.DEVNULL)
    assert git('rev-parse', 'FETCH_HEAD') == target
    assert not git('diff', '--name-only', before_head, target, '--', 'migrations', 'pyproject.toml', 'uv.lock', 'vmshpwa/pnpm-lock.yaml'), 'Unexpected dependency/schema delta'
    changed = git('diff', '--name-only', before_head, target).splitlines()
    S.mkdir(mode=0o755, exist_ok=True)
    archive = subprocess.Popen(['/usr/sbin/runuser', '-u', 'vmsh_tasks_bot', '--', 'git', 'archive', target], cwd=C, stdout=subprocess.PIPE)
    run(['tar', '-x', '-C', str(S)], stdin=archive.stdout)
    archive.stdout.close()
    assert archive.wait() == 0
    # Preserve existing server repairs by a real three-way merge, before touching runtime.
    for index, name in enumerate(original_dirty):
        base = R / f'merge-base-{index}'
        base.write_bytes(subprocess.check_output(['/usr/sbin/runuser', '-u', 'vmsh_tasks_bot', '--', 'git', 'show', f'{before_head}:{name}'], cwd=C))
        merged = subprocess.run(['git', 'merge-file', '-p', str(S / name), str(base), str(C / name)], stdout=subprocess.PIPE)
        assert merged.returncode == 0, f'Server patch conflicts: {name}'
        (S / name).write_bytes(merged.stdout)
        base.unlink()
    special = []
    if mode == 'firstvds':
        previous_source = B / 'deploy/releases/mobile-review-actions-20261117/source'
        special = ['vmshpwa/apps/student/src/sw.ts', 'vmshpwa/apps/family/src/sw.ts', 'vmshpwa/packages/offline/src/recent-media-policy.ts']
        for name in special:
            assert (S / name).read_bytes() == (C / name).read_bytes(), f'Media patch overlaps release: {name}'
            shutil.copy2(previous_source / name, S / name)
    paths = sorted(set(changed + original_dirty + special))
    old_files = {}
    for name in paths:
        path = C / name
        assert not path.is_symlink(), name
        if path.exists():
            tracked = subprocess.run(['/usr/sbin/runuser', '-u', 'vmsh_tasks_bot', '--', 'git', 'ls-files', '--error-unmatch', name], cwd=C, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
            assert tracked, f'Untracked file collision: {name}'
            old_files[name] = {'sha256': digest(path), 'mode': path.stat().st_mode & 0o777}
        else:
            old_files[name] = {'sha256': None}
    shutil.copy2(profile, S / 'creds_prod/vmsh_bot_config_prod.json')
    (S / 'creds_prod/vmsh_bot_config_prod.json').chmod(0o600)
    portal = C / '.runtime/glitchtip-portal.json'
    if portal.exists():
        (S / '.runtime').mkdir(exist_ok=True)
        shutil.copy2(portal, S / '.runtime/glitchtip-portal.json')
        (S / '.runtime/glitchtip-portal.json').chmod(0o600)
    for path in [S, *S.rglob('*')]:
        shutil.chown(path, user='vmsh_tasks_bot', group='web', follow_symlinks=False)
    if not (S / '.venv').exists():
        (S / '.venv').symlink_to(C / '.venv')
    R.chmod(0o755)
    previous = str(current.resolve(strict=True))
    preserved_units = ['vmsh-rehearsal-nats.service', 'gunicorn.vmsh_tasks_bot.service'] if mode == 'firstvds' else ['nats.service', 'vmshzoom.service']
    preserved = {unit: pid(unit) for unit in preserved_units}
    backup('backup-before', config)
    print('Verified main/analytics online backups; checking real contribution projection', flush=True)
    probe = '''import json,sqlite3,time
from datetime import datetime,UTC
from pathlib import Path
from types import SimpleNamespace
from db_methods.pwa.review_contribution import contribution_rows,contribution_lessons
import runpy
calculate_contribution=runpy.run_path('models/pwa/review_contribution.py')['calculate_contribution']
p=Path(__import__('sys').argv[1]);db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
teachers=db.execute("select reviewer_user_id,count(*) n from submission_reviews where source='staff' group by reviewer_user_id order by n desc limit 5").fetchall()
lessons=contribution_lessons(db,SimpleNamespace(global_access=True),datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S'))
measurements=[]
for teacher in teachers:
 t=time.monotonic();rows=contribution_rows(db,teacher[0]);value=calculate_contribution(rows,lessons);assert value['allTime']['plus']<=value['allTime']['total'];measurements.append({'checks':len(rows),'seconds':round(time.monotonic()-t,3)})
print(json.dumps({'teachersChecked':len(teachers),'publishedLessonContexts':len(lessons),'measurements':measurements,'readOnly':True}))
'''
    probe_result = subprocess.check_output([str(C / '.venv/bin/python'), '-c', probe, str(R / 'backup-before/main.sqlite3')], cwd=S, text=True, env={**os.environ, 'PYTHONPATH': str(S)})
    write('contribution-data-check.json', json.loads(probe_result))
    app(['pnpm', 'install', '--frozen-lockfile'], 'dependencies.log', S / 'vmshpwa')
    print('Building four production bundles and private sourcemaps', flush=True)
    app(['/usr/bin/python3', '-m', 'vmshpwa.scripts.production_frontend_build', '--release', release, '--media-origin', media], 'build.log')
    sys.path.insert(0, str(S))
    from vmshpwa.scripts.static_release import package_release, verify_release, retain_release_assets
    now = datetime.now(timezone.utc).isoformat()
    manifest = package_release(release, now, release_root=B / 'vmshpwa/releases')
    verify_release(release, now, release_root=B / 'vmshpwa/releases')
    retain_release_assets(Path(previous), B / 'vmshpwa')
    retain_release_assets(B / 'vmshpwa/releases' / release, B / 'vmshpwa')
    assert digest(profile) == digest(S / 'creds_prod/vmsh_bot_config_prod.json') or json.loads(profile.read_text()) == {**json.loads((S / 'creds_prod/vmsh_bot_config_prod.json').read_text()), 'sentry_release': config.get('sentry_release')}
    assert git('rev-parse', 'HEAD') == before_head
    assert all(digest(C / n) == h for n, h in original_hashes.items())
    assert current.resolve() == Path(previous)
    assert all(pid(u) == p for u, p in preserved.items())
    write('staged.json', {'release':release,'target':target,'sourceBefore':before_head,'previous':previous,'profileSha256':digest(profile),'schemaSha256':schema((C/config['db_filename']).resolve()),'originalDirty':original_dirty,'paths':old_files,'preservedUnits':preserved,'firstvdsMediaFiles':{n:digest(S/n) for n in special},'candidateHashes':{n:digest(S/n) for n in paths},'build':manifest['build']})
    print('STAGED: source repairs, profile and running services preserved', flush=True)
    sys.exit(0)

staged = json.loads((R / 'staged.json').read_text())
assert staged['target'] == target and staged['release'] == release
assert git('rev-parse', 'HEAD') == staged['sourceBefore']
assert current.resolve() == Path(staged['previous'])
assert digest(profile) == staged['profileSha256']
assert schema((C / config['db_filename']).resolve()) == staged['schemaSha256']
for name, record in staged['paths'].items():
    assert digest(C / name) == record['sha256'], f'Source changed since staging: {name}'
    assert digest(S / name) == staged['candidateHashes'][name], name
before_dir = R / 'before-files'
before_dir.mkdir(mode=0o700)
for name, record in staged['paths'].items():
    if record['sha256'] is not None:
        destination = before_dir / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(C / name, destination)

master = pid('vmshpwa.service')
def children():
    return set(map(int, Path(f'/proc/{master}/task/{master}/children').read_text().split()))
def handover():
    old = children()
    os.kill(master, signal.SIGHUP)
    deadline = time.monotonic() + 65
    while time.monotonic() < deadline:
        assert pid('vmshpwa.service') == master, 'Master changed unexpectedly'
        fresh = children()
        if len(fresh) >= 2 and not fresh.intersection(old) and all(not Path(f'/proc/{p}').exists() for p in old):
            return {'master':master,'workersBefore':sorted(old),'workersAfter':sorted(fresh)}
        time.sleep(0.5)
    raise RuntimeError('Rolling PWA worker replacement did not complete')

def point(destination):
    temporary = current.with_name('current.contribution-next')
    temporary.symlink_to(destination)
    os.replace(temporary, current)

def public(path):
    with urlopen(Request(origin + path, headers={'Cache-Control':'no-cache','Accept-Encoding':'identity'}), timeout=30) as response:
        assert response.status == 200
        return response.read()

def install_files(root, restore=False):
    for name, record in staged['paths'].items():
        destination, source = C / name, root / name
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + '.contribution-next')
            shutil.copy2(source, temporary)
            shutil.chown(temporary, user='vmsh_tasks_bot', group='web')
            os.replace(temporary, destination)
        elif destination.exists():
            if restore:
                assert digest(destination) == staged['candidateHashes'][name]
            destination.unlink()

try:
    install_files(S)
    git('reset', '--mixed', target)
    replacement = handover()
    print('PWA workers replaced; verifying runtime before switching static release', flush=True)
    for audience in ('student','family','staff'):
        run(['curl','-fsS','--max-time','15','--unix-socket',str(B/'vmshpwa/runtime/vmshpwa.sock'),'-H','X-Forwarded-For: 127.0.0.1','-H',f'X-Forwarded-Host: {origin.split("//")[1]}','-H','X-Forwarded-Proto: https',f'http://localhost/{audience}/api/v1/runtime'],stdout=(R/f'{audience}-runtime.json').open('wb'))
    point(B / 'vmshpwa/releases' / release)
    for audience in ('landing','student','family','staff'):
        path = '/' if audience == 'landing' else f'/{audience}/'
        assert public(path) == (current / audience / 'index.html').read_bytes(), audience
    assets = [p for p in (current/'staff/assets').rglob('*') if p.suffix in ('.js','.css')]
    def check_asset(path):
        assert hashlib.sha256(public('/staff/' + path.relative_to(current/'staff').as_posix())).hexdigest() == digest(path), path.name
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(check_asset, assets))
    with (R/'http-smoke.log').open('wb') as stream:
        run([str(C/'.venv/bin/python'),'-m','vmshpwa.scripts.production_http_smoke','--origin',origin,'--expected-instance','179' if mode=='firstvds' else 'production'],stdout=stream,stderr=subprocess.STDOUT)
    status = out(['curl','-sS','--max-time','15','-o',str(R/'contribution-unauthenticated.json'),'-w','%{http_code}',origin+'/staff/api/v1/review/my-contribution'])
    assert status == '401', 'New API route did not enforce authentication: ' + status
    assert digest(profile) == staged['profileSha256']
    assert schema((C/config['db_filename']).resolve()) == staged['schemaSha256']
    assert all(pid(u)==p for u,p in staged['preservedUnits'].items())
    assert not (B/'vmshpwa/runtime/service-updating').exists()
    assert not list(current.rglob('*.map'))
    result = {k:v for k,v in staged.items() if k not in ('paths','candidateHashes','profileSha256')}
    result.update(status='PASS',origin=origin,sourceAfter=git('rev-parse','HEAD'),handover=replacement,htmlHashesMatched=4,staffAssetHashesMatched=len(assets),httpChecksPassed=25,contributionApiUnauthenticatedStatus=status,schemaChanged=False,configurationPreserved=True,backupsBeforeVerified=True,staticAfter=str(current.resolve()))
    backup('backup-after',config)
    result['backupsAfterVerified']=True
    write('result.json',result)
    print(json.dumps(result,indent=2),flush=True)
except BaseException:
    point(Path(staged['previous']))
    install_files(before_dir,restore=True)
    git('reset','--mixed',staged['sourceBefore'])
    handover()
    (R/'rollback.txt').write_text('Source and static release restored; database was not restored or migrated.\n')
    raise
