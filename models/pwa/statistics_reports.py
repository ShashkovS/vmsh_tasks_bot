"""Current credit and historical review workload (docs/lesson-statistics.md)."""

from collections import defaultdict


CHANNELS = {1: "bot", 2: "written", 3: "zoom", 4: "school"}


def build_reports(facts, allowed_groups, lesson_number=None, *, include_table=True):
    problems, results, submitted, reviews, pending, students = facts
    problems = [p for p in problems if p["group_public_id"] in allowed_groups]
    by_id = {p["problem_id"]: p for p in problems}
    current = {}
    participants = defaultdict(set)
    for row in [*results, *submitted, *reviews, *pending]:
        if row["problem_id"] in by_id:
            participants[by_id[row["problem_id"]]["lesson_number"]].add(
                row["student_user_id"]
            )
    for row in results:
        if row["problem_id"] not in by_id:
            continue
        key = row["student_user_id"], row["problem_id"]
        # A test recheck keeps the attempt timestamp but writes a new result.
        # Attribution follows that verdict event; analytics retains attempt order.
        priority = (
            float(row["verdict_weight"]),
            str(row.get("source_ts") or row["ts"]),
            row.get("source_result_id") or row["result_id"],
        )
        old = current.get(key)
        if old is None or priority > old[0]:
            weight = float(row["verdict_weight"])
            current[key] = (
                priority,
                {
                    "score": 1 if weight >= 0.8 else 0.5 if weight > 0 else 0,
                    "source": CHANNELS[row["res_type"]],
                },
            )
    pending_pairs = {
        (r["student_user_id"], r["problem_id"])
        for r in pending
        if r["problem_id"] in by_id
    }
    tried_pairs = {
        (r["student_user_id"], r["problem_id"])
        for r in [*submitted, *reviews]
        if r["problem_id"] in by_id
    }
    numbers = sorted({p["lesson_number"] for p in problems})
    # Index once; scoped-reads-20261013.md removes lesson × history scans.
    columns_by_lesson = defaultdict(list)
    reviews_by_lesson = defaultdict(set)
    pending_by_lesson = defaultdict(int)
    credit_by_lesson = defaultdict(list)
    for problem in problems:
        columns_by_lesson[problem["lesson_number"]].append(problem)
    for review in reviews:
        problem = by_id.get(review["problem_id"])
        if problem is not None:
            reviews_by_lesson[problem["lesson_number"]].add(review["result_id"])
    for _, pid in pending_pairs:
        pending_by_lesson[by_id[pid]["lesson_number"]] += 1
    for (student, pid), (_, cell) in current.items():
        credit_by_lesson[by_id[pid]["lesson_number"]].append((student, pid, cell))
    summaries = []
    for number in numbers:
        row = dict(
            lessonNumber=number,
            students=len(participants[number]),
            allPlus=0,
            botPlus=0,
            writtenPlus=0,
            writtenWrittenPlus=0,
            writtenOralPlus=0,
            zoomPlus=0,
            schoolPlus=0,
            writtenChecked=len(reviews_by_lesson[number]),
            writtenPending=pending_by_lesson[number],
        )
        row["writtenTotal"] = row["writtenChecked"] + row["writtenPending"]
        channel_students = defaultdict(set)
        for student, pid, cell in credit_by_lesson[number]:
            if cell["score"] == 0:
                continue
            score, source = cell["score"], cell["source"]
            row["allPlus"] += score
            row[source + "Plus"] += score
            channel_students[source].add(student)
            if source == "written":
                if by_id[pid]["problem_type"] == 2:
                    row["writtenWrittenPlus"] += score
                elif by_id[pid]["problem_type"] in (3, 4):
                    row["writtenOralPlus"] += score
        for source in ("written", "zoom", "school"):
            row[source + "Students"] = len(channel_students[source])
        summaries.append(row)
    selected = (
        lesson_number if lesson_number is not None else max(numbers, default=None)
    )
    columns = columns_by_lesson[selected]
    rows = []
    for sid in sorted(
        participants[selected] if include_table else [],
        key=lambda sid: (
            (students[sid]["surname"] or "").casefold(),
            (students[sid]["name"] or "").casefold(),
            sid,
        ),
    ):
        cells = []
        for p in columns:
            key = sid, p["problem_id"]
            value = current.get(key)
            cells.append(
                {
                    "score": value[1]["score"] if value else 0,
                    "source": value[1]["source"] if value else None,
                    "attempted": value is not None
                    or key in tried_pairs
                    or key in pending_pairs,
                    "pending": key in pending_pairs,
                }
            )
        rows.append(
            dict(
                studentId=students[sid]["public_id"],
                name=students[sid]["display_name"],
                cells=cells,
                total=sum(c["score"] for c in cells),
            )
        )
    return dict(
        lessons=summaries,
        lessonNumbers=numbers,
        lessonNumber=selected,
        problems=[
            dict(
                problemId=p["public_id"],
                label=f"{p['prob']}{p['item'] or ''}",
                title=p["title"] or "",
            )
            for p in columns
        ],
        rows=rows,
    )
