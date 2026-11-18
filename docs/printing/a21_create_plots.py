# -*- coding: utf-8 -*-
"""Build personal PNG charts from the portal; docs/printing/legacy-api.md."""

import argparse
import os
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

from z_portal_print import get_portal_plot_data

# Итоги какого занятия обрабатываем (можно переопределить через --lesson).
use_lesson = 3
NEED_LAST = True
NEED_MIN = 3
NUM_PROC = 7
SCRIPT_DIR = Path(__file__).resolve().parent


def plot_stud_stat(task):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    data, name, cur_les, output_dir = task
    lessons = [int(row['lesson']) for row in data]
    print(f'{name}...')
    group_ids = [row['group_id'] for row in data]
    simple_prob_strength = [float(row['simple_prob_strength']) for row in data]
    compl_prob_strength = [float(row['compl_prob_strength']) for row in data]
    max_compl_prob_strength = [float(row['max_compl_prob_strength']) for row in data]
    simple_prob_strength_3 = [float(row["simple_smooth"]) if row["simple_smooth"] is not None else float("nan") for row in data]
    compl_prob_strength_3 = [float(row["complex_smooth"]) if row["complex_smooth"] is not None else float("nan") for row in data]
    solved = [row['solved'] for row in data]
    tot_problems = [row['tot_problems'] for row in data]
    solved_str = [f"{s}/{t}" for s, t in zip(solved, tot_problems)]
    fig, ax = plt.subplots(figsize=(6.5 + 8 * cur_les / 35, 4.5))
    ax.plot(lessons, simple_prob_strength_3, color='green', linewidth=10, alpha=0.2, label='_nolegend_', zorder=1)
    ax.plot(lessons, compl_prob_strength_3, color='orange', linewidth=10, alpha=0.2, label='_nolegend_', zorder=1)
    ax.plot(lessons, simple_prob_strength, marker='o', label='Простые задачи', color='green')
    ax.plot(lessons, compl_prob_strength, marker='o', label='Сложные задачи', color='orange')
    # https://matplotlib.org/stable/gallery/lines_bars_and_markers/linestyles.html
    ax.plot(lessons, max_compl_prob_strength, linestyle=(0, (1, 10)), linewidth=0.5, marker='*', label='Сложность занятия', color='blue')

    for i, (group_id, solve_str) in enumerate(zip(group_ids, solved_str)):
        ax.annotate(group_id, (lessons[i], 0), textcoords="offset points", xytext=(0, -27), ha='center')
        ax.annotate(solve_str, (lessons[i], 0), textcoords="offset points", xytext=(0, -40), ha='center')

    ax.set_ylabel('0=ничего не получается;\n10=получается любая задача')
    ax.set_title('Насколько хорошо получается решать\nпростые и сложные задачи')
    ax.legend()
    ax.grid(True)
    ax.set_ylim([0, 10])
    ax.set_xlim([1, cur_les] if cur_les > 1 else [0.5, 1.5])
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.set_xticks(range(1, cur_les + 1))
    fig.tight_layout()
    dst = Path(output_dir) / f"{name}.png"
    fig.savefig(dst, format='png', dpi=160)
    plt.close(fig)



def gen_tasks(rows, lesson, output_dir, *, need_last=NEED_LAST, need_min=NEED_MIN):
    """Group by identity; smooth and raw values share the same lesson row."""
    by_student = defaultdict(list)
    for row in rows:
        if 1 <= int(row["lesson"]) <= lesson:
            by_student[int(row["student_id"])].append(row)
    tasks = []
    for student_id, data in sorted(by_student.items()):
        data.sort(key=lambda row: int(row["lesson"]))
        lessons = {int(row["lesson"]) for row in data}
        if len(lessons) != len(data):
            raise RuntimeError(f"Повторные данные занятия для ученика {student_id}")
        if (need_last and lesson not in lessons) or len(lessons) < need_min:
            continue
        tasks.append((data, student_id, lesson, str(output_dir)))
    return tasks


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Нужно положительное число")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", type=positive_int, default=use_lesson)
    parser.add_argument("--event-id", help="Опорное событие; по умолчанию выбирается автоматически")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--processes", type=positive_int, default=NUM_PROC)
    parser.add_argument("--min-lessons", type=positive_int, default=NEED_MIN)
    parser.add_argument("--include-absent", action="store_true", help="Включить пропустивших целевое занятие")
    args = parser.parse_args()
    # VMSH_PRINT_API_TOKEN may override the existing private legacy config.
    token = os.environ.get("VMSH_PRINT_API_TOKEN")
    if not token:
        try:
            from z_CREDENTIALS import PORTAL_PRINT_API_TOKEN
            token = PORTAL_PRINT_API_TOKEN
        except ImportError:
            parser.error("Задайте VMSH_PRINT_API_TOKEN или PORTAL_PRINT_API_TOKEN в z_CREDENTIALS.py")
    try:
        payload = get_portal_plot_data(args.lesson, token=token, event_id=args.event_id)
        output_dir = args.output or SCRIPT_DIR / "shashkov_mail_sender" / f"Рез {args.lesson:02}" / "stat"
        tasks = gen_tasks(
            payload["rows"], args.lesson, output_dir,
            need_last=NEED_LAST and not args.include_absent, need_min=args.min_lessons,
        )
    except (RuntimeError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Расчёт {payload['runId']} от {payload['calculatedAt']}; графиков: {len(tasks)}")
    if not tasks:
        print("Нет учеников, удовлетворяющих фильтрам; проверьте номер занятия и дату расчёта.")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.processes == 1:
        for task in tasks:
            plot_stud_stat(task)
    else:
        with Pool(processes=min(args.processes, len(tasks))) as pool:
            pool.map(plot_stud_stat, tasks)
    print(f"Готово: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
