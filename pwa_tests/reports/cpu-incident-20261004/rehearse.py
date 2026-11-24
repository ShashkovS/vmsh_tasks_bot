"""Bounded read-only SQL parity; vmshpwa/docs/cpu-incident-20261004.md."""

import ast
import base64
import json
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def assignment(path, name):
    return next(node.value for node in ast.parse(path.read_text()).body
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == name
                    for target in node.targets))


ctes = ast.literal_eval(assignment(
    ROOT / "db_methods/pwa/effective_results.py", "STUDENT_EFFECTIVE_RESULTS_CTES",
))
expression = assignment(ROOT / "db_methods/pwa/content.py", "_STUDENT_PROBLEM_LIST_SELECT")
candidate = eval(compile(ast.Expression(expression), "query", "eval"),
                 {"STUDENT_EFFECTIVE_RESULTS_CTES": ctes})
argument = base64.b64encode(candidate.encode()).decode()
PROBE = r'''
import ast, base64, json, sqlite3, sys, time
from pathlib import Path
root = Path('/web/vmsh_tasks_bot/vmsh_tasks_bot')
tree = ast.parse((root / 'db_methods/pwa/content.py').read_text())
original = next(ast.literal_eval(node.value) for node in tree.body
    if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
    and target.id == '_STUDENT_PROBLEM_LIST_SELECT' for target in node.targets))
candidate = base64.b64decode(sys.argv[1]).decode()
db = sqlite3.connect(f'file:{root}/db/production_v2.db?mode=ro', uri=True)
db.execute('PRAGMA query_only = ON')
db.execute('BEGIN')
students = [row[0] for row in db.execute(
    'SELECT DISTINCT student_id FROM results ORDER BY id DESC LIMIT 3')]
scopes = db.execute("""
    SELECT course.public_id, group_record.public_id, lesson.public_id
    FROM group_lessons lesson
    JOIN courses course ON course.id = lesson.course_id
    JOIN groups group_record ON group_record.course_id = lesson.course_id
        AND group_record.group_id = lesson.group_id
    JOIN lesson_publications publication ON publication.group_lesson_id = lesson.id
        AND publication.kind = 'condition' AND publication.state = 'published'
    WHERE lesson.status = 'active'
    ORDER BY lesson.id DESC LIMIT 5
""").fetchall()
report = {'sqlite_version': sqlite3.sqlite_version, 'database_mode': 'read-only',
          'snapshot': True, 'deadline_seconds_per_query': 2, 'cases': []}
for case, (student, scope) in enumerate((student, scope) for student in students for scope in scopes):
    params = dict(student_user_id=student, course_public_id=scope[0],
                  group_public_id=scope[1], group_lesson_public_id=scope[2])
    record = {'case': case, 'measurements': {}}
    expected = None
    for name, sql in [('original', original), ('candidate', candidate)]:
        deadline = time.monotonic() + 2
        steps = [0]
        def progress():
            steps[0] += 1000
            return int(time.monotonic() > deadline)
        db.set_progress_handler(progress, 1000)
        started = time.perf_counter()
        rows = db.execute(sql, params).fetchall()
        elapsed = time.perf_counter() - started
        db.set_progress_handler(None, 0)
        if expected is None:
            expected = rows
        assert rows == expected, f'Rows changed in case {case}'
        record['measurements'][name] = dict(ms=round(elapsed * 1000, 3),
                                           vm_steps=steps[0], rows=len(rows))
    report['cases'].append(record)
plan = [row[3] for row in db.execute('EXPLAIN QUERY PLAN ' + candidate, params)]
assert not any(detail.startswith(('SCAN r ', 'SCAN c ')) for detail in plan)
report.update(all_rows_identical=True, global_result_cell_scans=False,
              candidate_plan=plan)
db.close()
print(json.dumps(report, indent=2))
'''
result = subprocess.run(
    ["ssh", "-F", "ssh/config", "-o", "BatchMode=yes", "vmshbegetagent",
     "python3 - " + shlex.quote(argument)],
    input=PROBE, text=True, capture_output=True, check=True, cwd=ROOT,
)
destination = Path(__file__).with_name("rehearsal.json")
destination.write_text(result.stdout)
report = json.loads(result.stdout)
print(json.dumps({"cases": len(report["cases"]), "all_rows_identical": True,
                  "output": str(destination),
                  "original_ms": [case["measurements"]["original"]["ms"] for case in report["cases"]],
                  "candidate_ms": [case["measurements"]["candidate"]["ms"] for case in report["cases"]]}, indent=2))
