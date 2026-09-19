"""Unweighted current scores; independent from model snapshots (lesson-statistics.md)."""

from collections import defaultdict


def summarize_lessons(problems, results, pending, allowed_groups):
    problems = [p for p in problems if p["group_public_id"] in allowed_groups]
    by_id = {p["problem_id"]: p for p in problems}
    scores = defaultdict(float)
    participants = defaultdict(set)
    tried = defaultdict(set)
    for row in [*results, *pending]:
        problem = by_id.get(row["problem_id"])
        if problem is None:
            continue
        student = row["student_user_id"]
        key = (problem["lesson_number"], problem["group_public_id"])
        participants[key].add(student)
        tried[problem["problem_id"]].add(student)
        weight = float(row.get("verdict_weight", 0))
        # Same accepted/partial boundary as models/pwa/progress.py; normalize
        # legacy fine-grained marks to the current three-state UI.
        score = 1.0 if weight >= 0.8 else 0.5 if weight > 0 else 0.0
        scores[(student, problem["problem_id"])] = max(
            scores[(student, problem["problem_id"])], score
        )
    lessons = {}
    for problem in problems:
        number, group_id = problem["lesson_number"], problem["group_public_id"]
        groups = lessons.setdefault(number, {})
        if group_id not in groups:
            groups[group_id] = {
                "groupId": group_id,
                "code": problem["group_code"],
                "name": problem["group_name"],
                "participantCount": len(participants[(number, group_id)]),
                "distribution": [],
                "problems": [],
            }
        group = groups[group_id]
        points = sum(
            scores[(student, problem["problem_id"])]
            for student in tried[problem["problem_id"]]
        )
        group["problems"].append(
            {
                "problemId": problem["public_id"],
                "label": f"{number}{problem['group_code']}.{problem['prob']}{problem['item'] or ''}",
                "title": problem["title"] or "",
                "points": points,
                "tried": len(tried[problem["problem_id"]]),
                "share": 100 * points / group["participantCount"]
                if group["participantCount"]
                else None,
            }
        )
    for number, groups in lessons.items():
        for group_id, group in groups.items():
            ids = [
                p["problem_id"]
                for p in problems
                if p["lesson_number"] == number and p["group_public_id"] == group_id
            ]
            group["distribution"] = sorted(
                sum(scores[(student, pid)] for pid in ids)
                for student in participants[(number, group_id)]
            )
    return [
        {"lessonNumber": number, "groups": list(groups.values())}
        for number, groups in sorted(lessons.items())
    ]
