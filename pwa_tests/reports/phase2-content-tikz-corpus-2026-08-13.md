# Статический прогон TikZ-корпуса ВМШ

Прогон использует production parser `vmsh-latex-compiler/3` и
нормализацию `tikz-c14n-v1`. TeX/PDF/SVG не компилировались,
S3 и БД не изменялись. Рекурсивно просмотрены только маски
`usl-??-?.tex` и `usl-??-?-sol.tex` с переходом по симлинкам.

## Итог

- TeX-файлов: **2184**;
- файлов с активным TikZ: **1140**;
- активных TikZ: **3598**
  ({'environment': 1214, 'inline': 85, 'wrapper': 2299});
- закомментированных `tikzpicture`, правильно исключённых: **692**;
- активных по строке, но исключённых как document tail или тело macro-definition:
  **136**;
- уникальных после минимальной нормализации: **2212**;
- повторных вхождений: **1386**;
- статических ошибок подготовки standalone: **1**;
- TikZ, не дошедших до semantic AST: **0**;
- внешних ссылок из TikZ: **1082**, найдено в банке
  **1082**, не найдено
  **0**, динамических
  **2**.

Corpus-set SHA-256: `8de58e262c5ee0a45ac42b8acef3734bd89c303fd2fcd596e5abeacf94498e71`.

## Подключённый контекст

- `addToTikz`: 218
- `chess-compat`: 19
- `def`: 34
- `definecolor`: 258
- `newcommand`: 263
- `newlength`: 4
- `pgfdeclarepatternformonly`: 4
- `setcounter`: 5
- `setlength`: 4
- `tikzset`: 88
- `usetikzlibrary`: 2492

## Проблемы TikZ-сканера

- `tikz.add_to_tikz_unclosed`: 2

## Blocking diagnostics общего parser

- `latex.command_forbidden`: 2
- `latex.dangling_backslash`: 95
- `latex.group_unclosed`: 250
- `latex.no_problems`: 9
- `latex.structure_in_inline_group`: 162
- `latex.unknown_macro`: 3508
- `source.replacement_character`: 7
- `telegram.derivative_invalid`: 1
- `web.derivative_invalid`: 1

## Все статические ошибки TikZ

| Файл | Строка | Код | Сообщение |
| --- | ---: | --- | --- |
| `ВМШ 2025-2026 5-7/usl-11-x-sol.tex` | 144 | `tikz.add_to_tikz_unclosed` | Маркер % addToTikz не имеет парного закрывающего маркера. |
| `ВМШ 2025-2026 5-7/usl-11-x.tex` | 113 | `tikz.add_to_tikz_unclosed` | Маркер % addToTikz не имеет парного закрывающего маркера. |
| `ВМШ 2025-2026 5-7/usl-16-x-sol.tex` | 355 | `asset.tikz_forbidden_command` | latex-to-pdf: TikZ source contains a file, dynamic or output primitive |

## Не найденные внешние файлы из TikZ (первые 100)

| Файл | Строка TikZ | Имя |
| --- | ---: | --- |
| — | — | нет |

Полные списки непредставленных TikZ, внешних ссылок и parser diagnostics
находятся в соседнем JSON. Этот отчёт является только статическим gate;
реальные ошибки TeX toolchain появятся на следующем шаге компиляции SVG.
