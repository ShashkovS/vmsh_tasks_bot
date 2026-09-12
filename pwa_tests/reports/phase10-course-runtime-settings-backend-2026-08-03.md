# Phase 10: backend настроек курса — 3 августа 2026

## Что реализовано

Добавлен первый внутренний owner для четырёх настроек `_BotSettings`, которые
действительно принадлежат курсу:

- шкала verdict;
- немедленный или отложенный показ результата;
- видимость прошлых листков;
- ограничение попыток тестовой задачи.

`reg_mode` остаётся глобальным legacy onboarding, game не входит в v1,
`save_sol_mode` не имеет replacement: новый pipeline всегда сохраняет content и
submissions. `_BotUIMsgs` остаётся versioned code resource до v2 i18n.

## Реализация

- migration:
  [`0077.pwa_course_runtime_settings.sql`](../../migrations/0077.pwa_course_runtime_settings.sql);
- typed whitelist/defaults:
  [`models/pwa/course_runtime_settings.py`](../../models/pwa/course_runtime_settings.py);
- короткие SQLite reads/writes:
  [`db_methods/pwa/course_runtime_settings.py`](../../db_methods/pwa/course_runtime_settings.py);
- admin-only HTTP GET/PUT, ETag и атомарный audit:
  [`apps/pwa_api/admin_course_routes.py`](../../apps/pwa_api/admin_course_routes.py).

До первой записи GET возвращает code-owned characterized defaults с version
`0`. PUT с matching `If-Match` создаёт version `1`; следующие записи увеличивают
version. Ответ явно сообщает `appliesAfter=restart`, поскольку Telegram
compatibility adapter может кешировать effective settings.

## Проверенные инварианты

- Teacher получает `403`, неизвестный курс — `404`;
- unknown/removed key, wrong enum и wrong type получают `422`;
- `saveSolMode` нельзя незаметно вернуть в новый JSON;
- stale или чужой ETag получает `409`;
- persisted JSON повторно проверяется typed policy и не заменяется defaults при
  повреждении;
- audit хранит before/after без credentials;
- synthetic audit failure откатывает первую settings row целиком;
- migration проходит `up → down → up` и `integrity_check`.

Focused gate: **29 PASS** вместе со schema inventory, migration lifecycle,
domain/API и существующим course catalog. Ruff и `git diff --check` — PASS.
Полный shared-worktree PWA Python gate: **1646 PASS / 6 intentional skips** за
**76,58 с** в восьми workers. В нём присутствовали параллельные незакоммиченные
изменения enrollment batch, поэтому это общий regression signal, а не
доказательство включения тех изменений в данный коммит.

## Открытая граница

Это backend slice, не Google cutover. Ещё нужны Zod/client, Staff editor,
Telegram compatibility read с course context, production mapping первого курса
и owner rehearsal. Legacy `/update_bot_settings` остаётся recovery path.
