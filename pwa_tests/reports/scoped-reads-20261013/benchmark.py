"""Alternating old/new callbacks on an isolated copy; no personal data in report."""
import asyncio
import argparse
import ast
import hashlib
import json
import math
import sqlite3
import statistics
import subprocess
import time
from pathlib import Path
from types import ModuleType

from db_methods.pwa.live_marking import LIVE_CELLS_SQL, LIVE_VISITS_SQL
from db_methods.pwa.performance_guard import scoped_query_probes, check_database_performance
from db_methods.pwa.lesson_statistics import course_facts
from db_methods.pwa.statistics_reports import report_facts
from models.pwa.lesson_statistics import summarize_lessons
from models.pwa.statistics_reports import build_reports
from apps.pwa_api.statistics_cache import main_snapshot, report_snapshot, StatisticsReadCache
from db_methods.pwa.course_analytics import find_latest_completed_course_run, list_course_run_metrics
from db_methods.pwa.iterative_analytics import read_state
from models.pwa.staff_statistics import summarize_staff_course_metrics

ROOT = Path(__file__).resolve().parents[3]

def old_module(path):
    source = subprocess.check_output(['git', 'show', f'aae27430:{path}'], cwd=ROOT, text=True)
    module = ModuleType('reference')
    exec(compile(source, path, 'exec'), module.__dict__)
    return module, source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=20)
    args = parser.parse_args()
    assert args.database.resolve().is_relative_to((ROOT / '.runtime').resolve()), 'Use an isolated runtime copy'
    db = sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True)
    probes = {item.name: item for item in scoped_query_probes(db)}
    prefix = LIVE_CELLS_SQL[:LIVE_CELLS_SQL.index('scoped_logical_keys')]
    tail = LIVE_CELLS_SQL[LIVE_CELLS_SQL.index('scope AS ('):]
    global_cells = prefix + tail.replace('scoped_problem_members', 'result_problem_groups').replace('scoped_effective_results', 'effective_results')
    old_live, old_live_source = old_module('db_methods/pwa/live_marking.py')
    visit_node = next(node for node in ast.parse(old_live_source).body if isinstance(node, ast.FunctionDef) and node.name == 'visits')
    old_visits = next(node.value for node in ast.walk(visit_node) if isinstance(node, ast.Constant) and isinstance(node.value, str) and 'SELECT v.*' in node.value).replace('session_id=?', 'session_id=:session_id')
    old_facts, _ = old_module('db_methods/pwa/lesson_statistics.py')
    old_reports, _ = old_module('db_methods/pwa/statistics_reports.py')
    old_reports.course_facts = old_facts.course_facts
    old_summary, _ = old_module('models/pwa/lesson_statistics.py')
    old_report_model, _ = old_module('models/pwa/statistics_reports.py')
    def old_main(cid,allowed):
        run = find_latest_completed_course_run(db,course_id=cid)
        metrics = [] if run is None else list_course_run_metrics(db,run_id=run['id'])
        facts = old_facts.course_facts(db,cid)
        difficulty,_ = read_state(db,cid)
        basic = old_summary.summarize_lessons(*facts,allowed)
        by_public = {p['public_id']:p for p in facts[0]}
        for lesson in basic:
            for group in lesson['groups']:
                for problem in group['problems']:
                    values = difficulty.get(by_public[problem['problemId']]['logical_problem_key'])
                    problem['difficultyWeak'] = values[0] if values else None
                    problem['difficultyStrong'] = values[1] if values else None
        pids = {p['problem_id'] for p in facts[0] if p['group_public_id'] in allowed}
        students = {r['student_public_id']:dict(studentId=r['student_public_id'],name=r['student_name'],id=r['student_user_id']) for r in facts[1] if r['problem_id'] in pids}
        personal = {}
        for row in metrics:
            if row['group_public_id'] in allowed:
                personal.setdefault(row['student_user_id'],[]).append(dict(
                    lessonNumber=row['lesson_number'],groupCode=row['group_code'],simple=row['simple_strength'],complex=row['complex_strength'],difficulty=row['max_complex_strength'],simpleSmooth=row['simple_smooth'],complexSmooth=row['complex_smooth'],solved=row['solved_items'],total=row['total_items']))
        return dict(run=run,lessons=summarize_staff_course_metrics(metrics,allowed_group_public_ids=allowed),basic=basic,students=students,personal=personal)

    jobs = []
    for name in ('live-cell-scoped', 'live-board-scoped', 'live-visits-scoped'):
        probe = probes[name]
        old_sql = old_visits if name == 'live-visits-scoped' else global_cells
        jobs.append((name, lambda sql=old_sql,p=probe.parameters: [tuple(row) for row in db.execute(sql,p)],
                     lambda sql=probe.sql,p=probe.parameters: [tuple(row) for row in db.execute(sql,p)], old_sql, probe.sql, probe.parameters))
    db.row_factory = sqlite3.Row
    courses = [dict(row) for row in db.execute('SELECT c.id FROM courses c WHERE EXISTS(SELECT 1 FROM group_lessons gl JOIN lesson_publications lp ON lp.group_lesson_id=gl.id WHERE gl.course_id=c.id AND lp.state=\'published\')')]
    parity = {'courses': 0, 'group_filters': 0, 'lesson_filters': 0}
    for course in courses:
        cid = course['id']
        groups = frozenset(row['public_id'] for row in db.execute('SELECT public_id FROM groups WHERE course_id=?', (cid,)))
        original = old_facts.course_facts(db,cid)
        reports = old_reports.report_facts(db,cid)
        for allowed in (groups, *(frozenset([g]) for g in sorted(groups))):
            assert old_summary.summarize_lessons(*original, allowed) == summarize_lessons(*course_facts(db,cid,allowed_group_public_ids=allowed),allowed), 'Basic formula parity'
            expected = old_report_model.build_reports(reports,allowed)
            facts = report_facts(db,cid,allowed_group_public_ids=allowed)
            assert expected == build_reports(facts,allowed), 'Full report parity'
            parity['group_filters'] += 1
            for number in expected['lessonNumbers']:
                actual = build_reports(report_facts(db,cid,allowed_group_public_ids=allowed,lesson_number=number), allowed,number)
                reference = old_report_model.build_reports(reports,allowed,number)
                assert all(actual[key] == reference[key] for key in ('problems','rows','lessonNumber')), 'Plus-table parity'
                parity['lesson_filters'] += 1
        parity['courses'] += 1
        if len(jobs) == 3:
            jobs.append(('statistics-main',lambda cid=cid,allowed=groups:old_main(cid,allowed),lambda cid=cid,allowed=groups:main_snapshot(db,cid,allowed),None,None,None))
            jobs.append(('statistics-summary',
                lambda cid=cid,allowed=groups: old_report_model.build_reports(old_reports.report_facts(db,cid),allowed,include_table=False),
                lambda cid=cid,allowed=groups: build_reports(report_facts(db,cid,allowed_group_public_ids=allowed),allowed,include_table=False),None,None,None))
            group = frozenset([sorted(groups)[0]]) if groups else frozenset()
            numbers = [p['lesson_number'] for p in original[0] if p['group_public_id'] in group]
            number = max(numbers,default=None)
            jobs.append(('statistics-plus-table',
                lambda cid=cid,allowed=group,n=number: {k:v for k,v in old_report_model.build_reports(old_reports.report_facts(db,cid),allowed,n).items() if k in ('problems','rows','lessonNumber')},
                lambda cid=cid,allowed=group,n=number: {k:v for k,v in build_reports(report_facts(db,cid,allowed_group_public_ids=allowed,lesson_number=n),allowed,n).items() if k in ('problems','rows','lessonNumber')},None,None,None))
    results = {}
    for name, old, new, old_sql, new_sql, params in jobs:
        timings = {'old': [], 'new': []}
        reads = {'old': [], 'new': []}
        for run in range(args.rounds):
            output = {}
            for label, callback in ((('old',old),('new',new)) if run%2 == 0 else (('new',new),('old',old))):
                count = [0]
                db.set_trace_callback(lambda sql: count.__setitem__(0,count[0]+int(sql.lstrip().upper().startswith(('SELECT','WITH')))))
                started = time.perf_counter()
                output[label] = callback()
                timings[label].append(1000*(time.perf_counter()-started))
                reads[label].append(count[0])
                db.set_trace_callback(None)
            assert output['old'] == output['new'], name + ' parity'
        results[name] = {label:{'medianMs':round(statistics.median(values),3),'p95Ms':round(sorted(values)[math.ceil(.95*len(values))-1],3), 'reads':sorted(set(reads[label]))} for label,values in timings.items()}
        if old_sql:
            results[name]['plans'] = {label:[row[3] for row in db.execute('EXPLAIN QUERY PLAN '+sql,params)] for label,sql in [('old',old_sql),('new',new_sql)]}
    async def cache_proof():
        cache = StatisticsReadCache()
        cid = courses[0]['id'] if courses else None
        if cid is None:
            return {}
        groups = frozenset(row['public_id'] for row in db.execute('SELECT public_id FROM groups WHERE course_id=?',(cid,)))
        callbacks = {'main':lambda:main_snapshot(db,cid,groups),
                     'summary':lambda:report_snapshot(db,cid,groups,None,matrix=False),
                     'plus-table':lambda:report_snapshot(db,cid,frozenset([sorted(groups)[0]]),None,matrix=True)}
        proofs = {}
        for kind,callback in callbacks.items():
            key = (kind,'course',tuple(sorted(groups)))
            async def load():
                return callback()
            await cache.get(key,load)
            times, counts = [], []
            for _ in range(args.rounds):
                count = [0]
                db.set_trace_callback(lambda sql:count.__setitem__(0,count[0]+int(sql.lstrip().upper().startswith(('SELECT','WITH')))))
                started = time.perf_counter()
                await cache.get(key,load)
                times.append(1000*(time.perf_counter()-started))
                counts.append(count[0])
                db.set_trace_callback(None)
            assert set(counts)=={0}
            proofs[kind] = {'medianMs':round(statistics.median(times),3),'p95Ms':round(sorted(times)[math.ceil(.95*len(times))-1],3),'sqlReads':0}
        return {'views':proofs,'bytes':cache.cache.bytes,'entries':len(cache.cache.entries)}
    cache_hits = asyncio.run(cache_proof())
    db.close()
    report = {'schemaVersion':1,'reference':'aae27430','databaseSha256':hashlib.sha256(args.database.read_bytes()).hexdigest(), 'roundsPerVariant':args.rounds,'alternating':True,'parity':parity,'results':results,'guard':check_database_performance(args.database),'cacheHits':cache_hits,'personalDataIncluded':False}
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'parity':parity,'results':{k:{a:b for a,b in v.items() if a!='plans'} for k,v in results.items()}}))

if __name__ == '__main__':
    main()
