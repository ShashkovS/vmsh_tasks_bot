"""Dispatch a reviewed server-only rehearsal; never transfer production rows."""

import ast
import base64
import json
import shlex
import subprocess
import sys
import textwrap
from pathlib import Path


mode = sys.argv[1]
assert mode in {'vmsh', 'tlf'}
root = Path(__file__).resolve().parent
source = Path('db_methods/pwa/content.py').read_text()
repository = next(node for node in ast.parse(source).body
                  if isinstance(node, ast.ClassDef) and node.name == 'PwaContentRepository')
method = next(node for node in repository.body
              if isinstance(node, ast.AsyncFunctionDef) and node.name == 'resolve_source_and_append_revision')
payload = {'migration': base64.b64encode(Path('migrations/0113.content_upload_compiler_generation.py').read_bytes()).decode(),
           'method': textwrap.dedent(ast.get_source_segment(source, method))}
command = 'cd /web/vmsh_tasks_bot/vmsh_tasks_bot && .venv/bin/python -c ' + shlex.quote((root / 'rehearse.py').read_text()) + ' ' + mode
host = 'vmshbegetagent' if mode == 'vmsh' else 'tlfprepagent'
if mode == 'tlf':
    command = 'sudo -n -u vmsh_tasks_bot bash -c ' + shlex.quote(command)
result = subprocess.run(['ssh', '-F', 'ssh/config', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', host, command],
                        input=json.dumps(payload).encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if result.returncode:
    print(result.stderr.decode()[-4000:])
    raise SystemExit(result.returncode)
proof = json.loads(result.stdout.decode().splitlines()[-1])
(root / f'rehearsal-{mode}.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(proof, ensure_ascii=False))
