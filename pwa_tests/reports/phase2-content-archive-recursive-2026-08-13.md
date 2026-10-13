# Proof: рекурсивная проверка LaTeX-архивов

Дата: 13 августа 2026. Production compiler: `vmsh-latex-compiler/3`.

## Выборка и итог

- roots: `docs/deploy/ВМШ 2025-2026 5-7` и
  `docs/deploy/ВМШ 2013-2025 старые`;
- точная маска: `usl-??-?.tex` / `usl-??-?-sol.tex`;
- найдено **2184**, исключено U+FFFD **7**, проверено **2177**;
- роли: обычный файл — `condition`, только `-sol` — `solution`;
- найдено **25 827** problem nodes;
- итоговых failed sources **38**, blocking errors **3301**.

Полный список каждой ошибки со строкой и колонкой находится в
[`phase2-content-archive-all-errors.md`](phase2-content-archive-all-errors.md),
машиночитаемая версия —
[`phase2-content-archive-all-errors.json`](phase2-content-archive-all-errors.json).

## Что исправлено

- **47** TeX-файлов: явные незакрытые task/hint/answer/solution blocks,
  незакрытые layout groups, две math-опечатки, legacy `problem`, английские
  объявления и две неподдерживаемые опечатки `задачабк`;
- **44/47** исправленных файлов полностью прошли `pdflatex`;
- ещё **3/47** остановились только на ранее отсутствовавших image assets:
  `23-24_03n_Cubit_LD`, `22-23_07_Clock_LD`, `23-24_09_Coins_LD`.

Compiler расширен только общими bounded-конструкциями. `picture` пропускается с
warning до будущей конвертации в TikZ. Локальные DSL рисунков/домино,
динамический `csname` и другие узкие сценарии не добавлены.

## Проверки

```text
.venv/bin/python -m pytest pwa_tests/domain/test_content_compiler.py pwa_tests/test_content_archive_recursive_diagnostics.py -q
# 80 passed

.venv/bin/python vmshpwa/scripts/content_archive_recursive_diagnostics.py write
.venv/bin/python vmshpwa/scripts/content_archive_recursive_diagnostics.py check
```

Baseline до исправлений: **883** failed sources / **7413** blocking errors.
Итог: **38** / **3301**; **3295** остаточных ошибок — вызовы локальных
графических макросов, сосредоточенные в **34** источниках.
