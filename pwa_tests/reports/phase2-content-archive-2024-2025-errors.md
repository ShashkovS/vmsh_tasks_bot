# Ошибки LaTeX-корпуса ВМШ 2024–2025

Отчёт получен production-компилятором `vmsh-latex-compiler/3` из всех
верхнеуровневых `.tex` файлов owner-local архива `ВМШ 2024-2025 5-7 Чехлова Липинский Вербицкая`. Исходные
файлы и симлинк не изменялись.

## Итог

- источников условий/решений: **218**;
- найдено верхнеуровневых `.tex`: **254**;
- пропущено агрегатных placeholder-файлов: **36**
  (из них пустых: **27**);
- пустых файлов среди условий/решений: **0**;
- найденных задач: **2481**;
- файлов с blocking errors: **14**;
- blocking errors: **25**;
- corpus-set SHA-256: `318d6a23979a3cc97891a1672abdb5f0df2c884e072f5e7ea3a94d8ba8763ee3`.

## Коды ошибок

- `latex.dangling_backslash`: 2
- `latex.environment_unclosed`: 1
- `latex.environment_unsupported`: 3
- `latex.field_unclosed`: 3
- `latex.no_problems`: 8
- `latex.problem_unclosed`: 1
- `source.replacement_character`: 7

## Предупреждения

- `latex.table_figure_layout_flattened`: 1
- `latex.tikz_preamble_ignored`: 4

## Все ошибки

| Файл | Строка | Колонка | Код | Сообщение |
| --- | ---: | ---: | --- | --- |
| `usl-01-z-oral-sol.tex` | 10 | 17 | `latex.no_problems` | В источнике не найдено ни одной поддерживаемой команды задачи. |
| `usl-01-z-oral-sol.tex` | 17 | 1 | `latex.environment_unclosed` | Environment 'document' не закрыт. |
| `usl-02-x-sol.tex` | 5 | 2 | `source.replacement_character` | Source содержит символ замены U+FFFD (7158 вхождений) и уже повреждён до загрузки. |
| `usl-02-x-sol.tex` | 23 | 17 | `latex.no_problems` | В источнике не найдено ни одной поддерживаемой команды задачи. |
| `usl-02-x.tex` | 7 | 2 | `source.replacement_character` | Source содержит символ замены U+FFFD (2551 вхождений) и уже повреждён до загрузки. |
| `usl-02-x.tex` | 24 | 17 | `latex.no_problems` | В источнике не найдено ни одной поддерживаемой команды задачи. |
| `usl-03-x-sol.tex` | 395 | 1 | `latex.problem_unclosed` | Задача не имеет явной завершающей команды. |
| `usl-07-x-sol.tex` | 373 | 1 | `latex.field_unclosed` | Блок hint не имеет завершающей команды. |
| `usl-07-x-sol.tex` | 378 | 1 | `latex.field_unclosed` | Блок solution не имеет завершающей команды. |
| `usl-08-n.tex` | 9 | 2 | `source.replacement_character` | Source содержит символ замены U+FFFD (4556 вхождений) и уже повреждён до загрузки. |
| `usl-08-n.tex` | 20 | 17 | `latex.no_problems` | В источнике не найдено ни одной поддерживаемой команды задачи. |
| `usl-08-p.tex` | 6 | 2 | `source.replacement_character` | Source содержит символ замены U+FFFD (4429 вхождений) и уже повреждён до загрузки. |
| `usl-08-p.tex` | 17 | 17 | `latex.no_problems` | В источнике не найдено ни одной поддерживаемой команды задачи. |
| `usl-08-x-sol.tex` | 304 | 5 | `latex.environment_unsupported` | Environment 'picture' не поддерживается compiler. |
| `usl-08-x-sol.tex` | 388 | 5 | `latex.environment_unsupported` | Environment 'picture' не поддерживается compiler. |
| `usl-08-x-sol.tex` | 478 | 5 | `latex.environment_unsupported` | Environment 'picture' не поддерживается compiler. |
| `usl-08-x.tex` | 5 | 2 | `source.replacement_character` | Source содержит символ замены U+FFFD (7060 вхождений) и уже повреждён до загрузки. |
| `usl-08-x.tex` | 23 | 17 | `latex.no_problems` | В источнике не найдено ни одной поддерживаемой команды задачи. |
| `usl-10-x-sol.tex` | 5 | 2 | `source.replacement_character` | Source содержит символ замены U+FFFD (10588 вхождений) и уже повреждён до загрузки. |
| `usl-10-x-sol.tex` | 25 | 17 | `latex.no_problems` | В источнике не найдено ни одной поддерживаемой команды задачи. |
| `usl-10-x.tex` | 5 | 2 | `source.replacement_character` | Source содержит символ замены U+FFFD (9139 вхождений) и уже повреждён до загрузки. |
| `usl-10-x.tex` | 23 | 17 | `latex.no_problems` | В источнике не найдено ни одной поддерживаемой команды задачи. |
| `usl-15-x-sol.tex` | 378 | 1 | `latex.field_unclosed` | Блок hint не имеет завершающей команды. |
| `usl-24-p.tex` | 152 | 1 | `latex.dangling_backslash` | Одиночный обратный слеш не образует LaTeX-команду. |
| `usl-27-p.tex` | 361 | 76 | `latex.dangling_backslash` | Одиночный обратный слеш не образует LaTeX-команду. |

Машиночитаемые SHA-256, размеры, роли, encoding и end-position находятся в
`pwa_tests/reports/phase2-content-archive-2024-2025-errors.json`.
