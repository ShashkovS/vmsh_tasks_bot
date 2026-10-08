"""One a53 iteration, without legacy temp tables. See lesson-statistics.md."""

import math
from collections import defaultdict

from models.pwa.course_analytics import _best_problem_scores, _group_metric


def calculate_step(problems, results, previous_difficulty, previous_strength):
    problems = [dict(p) for p in problems if p["lesson_number"] > 0]
    by_id = {p["problem_id"]: p for p in problems}
    results = [
        {**by_id[r["problem_id"]], **r}
        for r in results
        if r["problem_id"] in by_id
        and r.get("trainable", True)
        and float(r["verdict_weight"]) >= 0
    ]
    difficulty = {
        p["logical_problem_key"]: previous_difficulty.get(
            p["logical_problem_key"], (0.5, 0.5)
        )
        for p in problems
    }
    for p in problems:
        p["for_weak"], p["for_strong"] = difficulty[p["logical_problem_key"]]
    scores, direct = _best_problem_scores(results)
    groups = defaultdict(list)
    for p in problems:
        groups[(p["lesson_number"], p["group_id"])].append(p)
    visits = {}
    # Match a53's selection weights (including its lesson-level denominator).
    for (student, lesson), candidates in direct.items():

        def preference(group):
            items = groups[(lesson, group)]
            count = len(items)
            weak = sum(p["for_weak"] for p in items)
            strong = sum(p["for_strong"] for p in items)
            simple_score = sum(
                scores.get((student, lesson, p["logical_problem_key"]), 0)
                * (1 - p["for_weak"])
                for p in items
            )
            complex_score = sum(
                scores.get((student, lesson, p["logical_problem_key"]), 0)
                * p["for_strong"]
                for p in items
            )
            rating = 2 * simple_score * 10000 / (
                9999 * (count - weak) + count
            ) + 3 * complex_score * 3 / (2 * strong + count)
            return (-rating, items[0]["group_sort_order"], group)

        visits[(student, lesson)] = min(candidates, key=preference)
    observations = defaultdict(dict)
    for (student, lesson), group in visits.items():
        for p in groups[(lesson, group)]:
            observations[student][p["logical_problem_key"]] = scores.get(
                (student, lesson, p["logical_problem_key"]), 0
            )
    strength = {
        student: previous_strength.get(student, (0.5, 0.5)) for student, _ in direct
    }
    skipped = 0

    def ratio(numerator, denominator, fallback):
        nonlocal skipped
        if denominator <= 0 or not math.isfinite(denominator):
            skipped += 1
            return fallback
        value = numerator / denominator
        if not math.isfinite(value):
            skipped += 1
            return fallback
        return min(1.0, max(0.0, value))

    for student, values in observations.items():
        solved = {key: score for key, score in values.items() if score >= 0.5}
        simple = ratio(
            sum(score * (1 - difficulty[key][0]) for key, score in solved.items())
            * 10000,
            9999 * sum(1 - difficulty[key][0] for key in values)
            + sum(difficulty[key][0] > 0 for key in values),
            strength[student][0],
        )
        complex_value = ratio(
            sum(score * difficulty[key][1] for key, score in solved.items()) * 3,
            2 * sum(difficulty[key][1] for key in values)
            + sum(difficulty[key][1] > 0 for key in values),
            strength[student][1],
        )
        strength[student] = (simple, complex_value)
    updated = {}
    for key, old in difficulty.items():
        tried = {
            student: values[key]
            for student, values in observations.items()
            if key in values
        }
        solved = {student: score for student, score in tried.items() if score >= 0.5}
        strong = 1 - ratio(
            20 * sum(score * strength[student][1] for student, score in solved.items()),
            19 * sum(strength[student][1] for student in tried)
            + sum(strength[student][1] > 0 for student in tried),
            1 - old[1],
        )
        weak = 1 - ratio(
            20
            * sum(
                score * (1 - strength[student][0]) for student, score in solved.items()
            ),
            19 * sum(1 - strength[student][0] for student in tried)
            + sum(strength[student][0] > 0 for student in tried),
            1 - old[0],
        )
        updated[key] = (weak, strong)
    for p in problems:
        p["for_weak"], p["for_strong"] = updated[p["logical_problem_key"]]
    metrics = []
    for (student, lesson), group in sorted(visits.items()):
        metric = _group_metric(
            groups[(lesson, group)], scores, student_id=student, lesson_number=lesson
        )
        metric["total_items"] = len(groups[(lesson, group)])
        # Pool the visited lesson facts in ±3, not an average of final ratios.
        window = []
        window_scores = {}
        for (sid, num), gid in visits.items():
            if sid != student or abs(num - lesson) > 3:
                continue
            for p in groups[(num, gid)]:
                key = f"{num}:{p['logical_problem_key']}"
                window.append({**p, "logical_problem_key": key})
                window_scores[(student, lesson, key)] = scores.get(
                    (student, num, p["logical_problem_key"]), 0
                )
        smooth = _group_metric(
            window, window_scores, student_id=student, lesson_number=lesson
        )
        metrics.append(
            {
                "student_user_id": student,
                "lesson_number": lesson,
                "group_id": group,
                **metric,
                "simple_smooth": smooth["simple_strength"],
                "complex_smooth": smooth["complex_strength"],
            }
        )
    changes = [
        abs(a - b) for key in updated for a, b in zip(updated[key], difficulty[key])
    ]
    changes += [
        abs(a - b)
        for sid in strength
        for a, b in zip(strength[sid], previous_strength.get(sid, (0.5, 0.5)))
    ]
    return (
        updated,
        strength,
        metrics,
        {
            "skippedDenominators": skipped,
            "maxChange": max(changes, default=0),
            "students": len(strength),
            "problems": len(updated),
        },
    )
