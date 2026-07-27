# Phase 2E: problem matching and metadata review API proof

Дата проверки: 28 июля 2026 года.

Это промежуточный backend gate этапа 2. Он доказывает работу сопоставления
canonical LaTeX-задач с legacy `problems` и последующего metadata review, но не
закрывает Staff UI, Storybook visual approval или production-build E2E.

Авторитетные решения: `MATCH-01..03` и `METADATA-01` в
`vmshpwa/dev/development-plan/06-phase-2-content.md`.

## Реализованная граница

- `GET/PUT /staff/api/v1/content/revisions/{revisionId}/problem-matches` выдаёт
  canonical identities, same-lesson candidates и явные решения
  `auto_position | manual_match | insert_new | omit`.
- Один mutation batch обязан точно покрывать canonical problem list. Partial,
  duplicate, cross-lesson и неверный positional match отклоняются; вся запись
  выполняется одной `BEGIN IMMEDIATE` транзакцией.
- `GET/PUT /staff/api/v1/group-lessons/{groupLessonId}/metadata-grid` читает и
  подтверждает все non-omitted задачи exact revision. Path, revision и
  authoritative permission scope сверяются в SQLite.
- Review использует отдельный hash-derived ETag. Compile ETag не может случайно
  авторизовать grid mutation; stale write получает `409`, точный повтор уже
  подтверждённого полного batch не создаёт дублей.
- Metadata confirmation одной транзакцией создаёт immutable
  `problem_revisions` и обновляет текущую legacy `problems` projection. История
  result/submission не переписывается.
- Поддержаны все 23 исторических answer type. Test-задача требует answer type;
  письменная/устная задача не может сохранить скрытые test answer fields.
- Publish/schedule/rollback остаются fail-closed: успешный compile без полного
  matching и reviewed metadata возвращает `422 problem_review_incomplete`.
- Endpoint доступен admin с `content.manage`; Teacher получает `403`.

## Проверки

```text
uv run ruff check \
  apps/pwa_api/content_routes.py db_methods/pwa/content.py \
  models/pwa/content.py pwa_tests/domain/test_content.py \
  pwa_tests/integration/test_content_repository.py \
  pwa_tests/integration/test_content_http_api.py
PASS

uv run pytest -q \
  pwa_tests/domain/test_content.py \
  pwa_tests/integration/test_content_repository.py \
  pwa_tests/integration/test_content_http_api.py
110 passed

git diff --check -- <Phase 2E backend paths>
PASS
```

Тесты используют настоящий `aiohttp.web.Application`, auth middleware и
отдельную migrated/seeded SQLite. MSW, Telegram, Google, S3 и production
credentials не используются.

Покрыты happy path, полный batch, atomic rollback, `insert_new`, manual и
positional match, exact retry, stale conflict, wrong group-lesson scope,
Teacher `403`, невалидная комбинация task/answer fields, сохранность legacy
projection и разблокировка publication gate только после обоих review шагов.

## Оставшаяся работа этого gate

- строгие TypeScript/Zod contracts и API client;
- Staff workflow, восстановление после reload и понятные cell diagnostics;
- Storybook matching/grid interaction states, a11y и owner visual review;
- production-build Playwright flow upload → matching → metadata → publish.

До Phase 3 Staff-only wire временно использует legacy integer `problemId` как
candidate token. Student/Family его не получают; opaque problem identity будет
введена вместе с task-list/detail API.
