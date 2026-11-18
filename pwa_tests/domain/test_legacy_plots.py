"""a21 keeps student/lesson identities aligned when plotting API rows."""

import importlib.util
from pathlib import Path
import sys

import pytest

from docs.printing import legacy_print_client


@pytest.fixture
def plots(monkeypatch):
    monkeypatch.setitem(sys.modules, "z_portal_print", legacy_print_client)
    path = Path(__file__).resolve().parents[2] / "docs/printing/a21_create_plots.py"
    spec = importlib.util.spec_from_file_location("legacy_plots", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sparse_unordered_history_filters_and_keeps_smooth_in_same_row(plots, tmp_path):
    rows = [
        {"student_id": student, "lesson": lesson, "simple_smooth": lesson / 2}
        for student, lesson in [(7, 3), (8, 1), (7, 1), (8, 2), (7, 2), (7, 4)]
    ]
    tasks = plots.gen_tasks(rows, 3, tmp_path)
    assert len(tasks) == 1
    data, student_id, lesson, _ = tasks[0]
    assert (student_id, lesson) == (7, 3)
    assert [(row["lesson"], row["simple_smooth"]) for row in data] == [(1, .5), (2, 1), (3, 1.5)]
    assert len(plots.gen_tasks(rows, 3, tmp_path, need_last=False, need_min=2)) == 2
    with pytest.raises(RuntimeError, match="Повторные данные"):
        plots.gen_tasks(rows + [rows[0]], 3, tmp_path)


def test_plot_png_handles_missing_smoothing_and_single_lesson(plots, tmp_path):
    pytest.importorskip("matplotlib")
    row = dict(student_id=7, lesson=1, group_id="н", simple_prob_strength=6,
               compl_prob_strength=4, max_compl_prob_strength=8,
               simple_smooth=None, complex_smooth=None, solved=2, tot_problems=5)
    plots.plot_stud_stat(([row], 7, 1, str(tmp_path)))
    image = tmp_path / "7.png"
    assert image.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert image.stat().st_size > 10000
