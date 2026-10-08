import ast
from pathlib import Path

import numpy as np
import pytest

from models.pwa.iterative_analytics import calculate_step
from models.pwa.lesson_statistics import summarize_lessons


def problem(pid, lesson=1, group="n", key=None):
    return dict(
        problem_id=pid,
        public_id=f"p-{pid}",
        lesson_number=lesson,
        group_id=group,
        group_public_id=group,
        group_code=group,
        group_name=group,
        group_sort_order=1,
        prob=pid,
        item="",
        title="Test",
        problem_type=2,
        logical_problem_key=key or str(pid),
    )


def result(pid, student=1, score=1, index=1):
    return dict(
        problem_id=pid,
        student_user_id=student,
        verdict_weight=score,
        result_id=index,
        ts=f"2026-09-{index:02}T12:00:00",
    )


def test_basic_points_pending_zero_duplicates_and_groups():
    problems = [problem(1, 0), problem(2, 0), problem(3, 0, "p")]
    results = [result(1, score=0.5), result(1, score=0.5), result(3)]
    pending = [dict(problem_id=2, student_user_id=2)]
    groups = summarize_lessons(problems, results, pending, {"n", "p"})[0]["groups"]
    assert groups[0]["participantCount"] == 2
    assert groups[0]["distribution"] == [0, 0.5]
    assert groups[0]["problems"][0]["points"] == 0.5
    assert groups[0]["problems"][0]["tried"] == 1
    assert groups[0]["problems"][0]["share"] == 25
    assert groups[1]["participantCount"] == 1


def test_removed_problem_and_corrected_verdict_are_not_counted():
    rows = summarize_lessons([problem(1)], [result(1, score=-1), result(99)], [], {"n"})
    assert rows[0]["groups"][0]["distribution"] == [0]
    assert rows[0]["groups"][0]["problems"][0]["points"] == 0


def test_no_submissions_and_group_scope():
    rows = summarize_lessons([problem(1), problem(2, group="p")], [], [], {"n"})
    assert len(rows[0]["groups"]) == 1
    assert rows[0]["groups"][0]["problems"][0]["share"] is None


def test_legacy_accepted_mark_matches_current_progress_status():
    rows = summarize_lessons([problem(1)], [result(1, score=0.95)], [], {"n"})
    assert rows[0]["groups"][0]["problems"][0]["points"] == 1


def test_zero_score_is_an_observation_but_pending_check_is_not():
    _, strength, metrics, _ = calculate_step([problem(1)], [result(1, score=0)], {}, {})
    assert strength[1] == (0, 0)
    assert len(metrics) == 1 and metrics[0]["solved_items"] == 0
    _, strength, metrics, _ = calculate_step(
        [problem(1)], [{**result(1), "trainable": False}], {}, {}
    )
    assert strength == {} and metrics == []


def test_one_iteration_matches_original_numpy_calc():
    # Extract only the pure legacy function, never import its script/config/main.
    tree = ast.parse(Path("_external_pipelines/a53_calc_rating_new.py").read_text())
    function = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "calc"
    )
    loop = next(n for n in function.body if isinstance(n, ast.For))
    loop.iter = ast.Call(
        func=ast.Name(id="range", ctx=ast.Load()),
        args=[ast.Constant(value=1)],
        keywords=[],
    )
    namespace = dict(
        np=np,
        SIMPLE_CALC_WEIGHT=9999,
        SIMPLE_ONE_WEIGHT=1,
        COMPL_CALC_WEIGHT=2,
        COMPL_ONE_WEIGHT=1,
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
            "<legacy-calc>",
            "exec",
        ),
        namespace,
    )
    data = np.array([[1, 0.5, 0], [0, 1, 1], [1, 0, 0.5]], dtype=float)
    old = np.full(3, 0.5)
    strong, weak, pupil_complex, pupil_simple = namespace["calc"](
        data, old.copy(), old.copy(), old.copy(), old.copy()
    )
    problems = [problem(i + 1) for i in range(3)]
    rows = [
        result(col + 1, row + 1, float(data[row, col]))
        for row in range(3)
        for col in range(3)
    ]
    difficulty, strength, metrics, _ = calculate_step(problems, rows, {}, {})
    for i in range(3):
        assert difficulty[str(i + 1)] == pytest.approx((weak[i], strong[i]))
        assert strength[i + 1] == pytest.approx((pupil_simple[i], pupil_complex[i]))
    assert len(metrics) == 3


def test_zero_lesson_empty_and_unobserved_keep_state():
    difficulty, strength, metrics, diagnostics = calculate_step(
        [problem(1), problem(2, 0)], [result(2)], {"1": (0.2, 0.7)}, {}
    )
    assert difficulty == {"1": pytest.approx((0.2, 0.7))}
    assert strength == {} and metrics == []
    assert diagnostics["skippedDenominators"] == 2


def test_test_attempt_penalty_is_not_applied_to_basic_points():
    p = {**problem(1), "problem_type": 1}
    rows = [result(1, score=0), result(1, score=1, index=2)]
    _, strength, _, _ = calculate_step([p], rows, {}, {})
    assert strength[1][0] < 1
    assert (
        summarize_lessons([p], rows, [], {"n"})[0]["groups"][0]["problems"][0]["points"]
        == 1
    )


def test_smoothing_uses_dynamic_window_and_excludes_absences():
    ps = [problem(1, 40), problem(2, 41), problem(3, 49)]
    _, _, metrics, _ = calculate_step(
        ps, [result(1), result(2, score=0.5), result(3)], {}, {}
    )
    assert [m["lesson_number"] for m in metrics] == [40, 41, 49]
    assert metrics[0]["simple_smooth"] == pytest.approx(metrics[1]["simple_smooth"])
    assert metrics[2]["simple_smooth"] == pytest.approx(metrics[2]["simple_strength"])
