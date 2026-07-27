# Phase 0 legacy characterization

Дата фиксации: 27 июля 2026 года.

Этот отчёт описывает только проверяемые исторические правила общего
Python/SQLite-контура. Он не объявляет legacy UX целевой моделью PWA. Исходные
данные школьников, фрагменты event logs и credentials в отчёт и fixtures не
копировались.

## Ответы на тестовые задачи

Источник истины на момент characterization:

- [`helpers/consts.py`](../../helpers/consts.py) — стабильные числовые ID 23
  значений `ANS_TYPE`, подписи и spreadsheet decoder;
- [`helpers/checkers.py`](../../helpers/checkers.py) — `fullmatch`-валидация,
  парсинг и сравнение;
- [`handlers/student_handlers.py`](../../handlers/student_handlers.py) — trim,
  custom validation, несколько правильных ответов и отдельный `SELECT_ONE` flow;
- [`test_legacy_answer_types.py`](../domain/test_legacy_answer_types.py) —
  исполняемая матрица.

Зафиксированы все 23 типа: digit, natural, integer, ratio, float, fraction,
mixed fraction, четыре варианта integer sequence, integer set, polynomial,
float with tolerance, time, date, weekday, fraction sequence, multiset, two
symbolic modes, select-one и string.

Критические различия:

- validation применяется к `student_answer.strip()` через `fullmatch`;
- последовательность сохраняет порядок, множество его игнорирует, multiset
  игнорирует порядок, но сохраняет кратность;
- time/date принимают исторические разделители и нормализуются списком чисел;
- `FLOAT_EPS` допускает обе границы интервала;
- `SELECT_ONE` и `STRING` не имеют стандартной regex; select-one проверяется
  отдельным списком видимых значений;
- strict symbolic checker принимает только `EQUAL`, equiv checker также
  принимает `MAY_BE`;
- polynomial вычисляется на `n=1..10`, ограничивает выражение и степень.

Доверенный `cor_ans_checker` с `exec` намеренно не запускается этим hermetic
набором: его sandbox/allowlist и historical programs требуют отдельного security
characterization до Staff metadata cutover.

## Вердикты, результаты и реакции

Исполняемый proof:
[`test_legacy_results_and_reactions.py`](../domain/test_legacy_results_and_reactions.py).

- Зафиксированы все ID, visual ticks и веса `0, 0.05, 0.25, 0.5, 0.7, 0.95,
  1.0`. `OLD_SOLVED=1` остаётся read-compatibility enum, но отсутствует в
  lookup-таблице после migration 0033; canonical persisted значение —
  `SOLVED=18`.
- Исторический `check_student_solved` включает любой положительный вес, а список
  решённых для UI использует порог `>=0.8`.
- Зафиксированы четыре семейства реакций: письменная/устная × ученик/учитель,
  их ID и связь письменной реакции с конкретным result.

## Письменная очередь и legacy synonyms

Исполняемый proof:
[`test_legacy_review_queue.py`](../domain/test_legacy_review_queue.py).

- Новая, просроченная более чем на 30 минут и уже взятая тем же учителем работа
  доступна для проверки; свежая аренда другого учителя недоступна.
- Claim использует условный update, выдача сортируется по времени и ограничена
  восемью работами; Staff group scope фильтрует через группу задачи.
- Отрицательный `problem_id` остаётся отдельным SOS-разделом.
- Legacy synonym projection склеивает одинаковое название внутри одинакового
  номера занятия, в том числе историческую форму с различной ценой `N⚡`; при
  `join=False` каждая задача снова содержит только собственный ID.

Это описание старого projection. Целевая модель курса хранит исходные задачи,
submissions и verdict раздельно, а логическое объединение ограничивает одним
`course_lesson`; она реализуется и тестируется в последующих фазах.

## История группы/режима и Telegram provenance

Исполняемый proof:
[`test_legacy_user_changes_and_telegram_linkage.py`](../domain/test_legacy_user_changes_and_telegram_linkage.py).

- `User.set_group_id` добавляет в `user_changes_log` строку `G` с исходным
  `group_id`, а `User.set_online_mode` — строку `O` со строковым десятичным
  значением `ONLINE_MODE` (`1` или `2`). Текущее значение пользователя и audit
  действительно сохраняются в SQLite.
- Legacy mutators пишут audit при каждом вызове, даже если значение уже было
  текущим. Поэтому будущий backfill не должен считать каждую строку настоящим
  переходом без сравнения с предыдущим состоянием.
- Telegram-origin сообщения письменной ветки сохраняют точные
  `written_tasks_discussions.chat_id` и `tg_msg_id`; `teacher_id` отличает
  комментарий преподавателя от сообщения школьника. Оба Telegram-поля nullable,
  поэтому тот же legacy storage API уже принимает сообщение без Telegram-origin.
- `results` не содержит `chat_id`, `tg_msg_id` или FK на discussion. Результат и
  сообщения исторически соединяются только общими `student_id + problem_id`;
  добавление результата не удаляет и не переписывает сообщения.

## Golden corpus

Файлы [`_vmsh_examples`](../../_vmsh_examples) представлены в
[`golden-manifest.json`](../../vmshpwa/fixtures/content/golden-manifest.json):

- 54 файла;
- занятия 21, 27, 39, 40 и 41;
- группы `n`, `p`, `x`;
- 30 TeX, 18 PDF и 6 JSON;
- TeX явно распознан как Windows-1251, JSON как UTF-8, PDF как binary;
- manifest хранит SHA-256, размер, роль и только структурные счётчики.

Генератор/validator:
[`golden_corpus.py`](../../vmshpwa/scripts/golden_corpus.py). Команда `check`
ничего не изменяет. Команда `write` атомарно обновляет только canonical manifest
и должна запускаться после содержательного просмотра изменившихся источников.
Proof [`test_legacy_golden_corpus.py`](../domain/test_legacy_golden_corpus.py)
проверяет полный охват, отсутствие content excerpts/абсолютных путей и stale hash.

## Ограничения baseline

- Raw logs не являются fixture; нагрузочные признаки из них оформляются только
  агрегатным workload report.
- Golden manifest обнаруживает source drift, но не доказывает визуальную
  эквивалентность TeX → PWA/Telegram/PDF; это отдельный converter visual gate.
- Проверка mathsolvers в этом наборе фиксирует решение `EQUAL`/`MAY_BE`, а не
  дублирует собственную тестовую матрицу внешней библиотеки.
