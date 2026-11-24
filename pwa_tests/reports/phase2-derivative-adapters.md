# Phase 2: PDF и Telegram Rich derivative adapters

Дата проверки: 27 июля 2026 года.

## Граница инкремента

Этот proof закрывает только два изолированных адаптера Phase 2:

- полная compiler-approved LaTeX revision → воспроизводимая PDF-производная;
- compiler-produced Telegram Rich HTML → transport-neutral
  send/edit/delete lifecycle.

Инкремент не меняет schema, HTTP API, frontend, publication state или legacy
Telegram polling. Он не является print workflow: PDF только создаётся как
immutable derivative для preview/regression. Исторические идеи сборки и печати
сверялись с `_external_pipelines/a12_dum_tex_files.py`,
`a13_print_per_aud_conds_tex.py` и `a14_zall_auds_pdf.py`, но эти скрипты не
импортируются production-кодом.

## PDF boundary

[`helpers/pwa/content/pdf.py`](../../helpers/pwa/content/pdf.py):

- требует успешный pure compiler gate для полного документа;
- отдельно probe-ит configured `pdflatex_path` и не хранит resolved absolute
  path в публичном probe/provenance;
- запускает один фиксированный argv через `create_subprocess_exec`, без shell,
  в одноразовом temporary directory;
- использует `-no-shell-escape`, `openin_any=p`, `openout_any=p`, timeout,
  bounded process output и предел PDF 64 MiB;
- не включает stderr/source/path в публичную ошибку timeout/non-zero/missing;
- проверяет `%PDF-` и завершающий `%%EOF`;
- фиксирует `SOURCE_DATE_EPOCH`, UTC, pdfTeX date metadata и trailer ID от
  source SHA-256. Два запуска representative fixture дают одинаковые bytes,
  SHA-256 и provenance;
- возвращает bytes только после успешной проверки, а temporary TeX/log/aux/PDF
  удаляются вместе с каталогом.

Representative fixture
[`phase2-derivative-document.tex`](../fixtures/content/phase2-derivative-document.tex)
— полный UTF-8 документ с формулой, списком, таблицей и TikZ. Он использует
поддерживаемые compiler aliases `\problem`/`\eproblem`, поэтому не зависит от
непоставляемого custom `newlistok.sty`.

Реальный opt-in local smoke прошёл через настроенный developer `pdflatex`:

```text
VMSH_RUN_CONTENT_PDF_SMOKE=1 VMSH_PDFLATEX_PATH=<configured executable> \
  pytest -q -n0 pwa_tests/integration/test_content_pdf_smoke.py
1 passed
```

Probe сообщает нормализованную версию `MiKTeX-pdfTeX 4.10 (MiKTeX 22.1)`;
machine path не сохраняется. MiKTeX требует доступ к своему owner-local state,
поэтому внутри ограниченного filesystem sandbox probe ожидаемо timeout-ится;
proof выполнен без сети, credentials и production/user data с доступом только
к уже установленному локальному toolchain.

## Telegram Rich boundary

[`helpers/pwa/content/telegram_publisher.py`](../../helpers/pwa/content/telegram_publisher.py)
принимает только `CompileResult`, который:

- не является `FULL_PREVIEW` и не имеет blocking diagnostics;
- содержит `telegram_html` текущего renderer version;
- сохранил исходный compiler SHA-256;
- повторно проходит canonical allowlist и неизменяемые Bot API 10.2 limits:
  32 768 characters, 500 blocks, nesting 16, 50 media и 20 table columns.

Publisher не знает token, config, default chat или binding. Destination всегда
передаётся явно. Transport protocol использует `send_rich_message`,
`edit_rich_message` и `delete_message`; returned message ID валидируется.
Aiogram 3.25 ещё не содержит generated `sendRichMessage`, поэтому
[`helpers/pwa/telegram_rich_aiogram.py`](../../helpers/pwa/telegram_rich_aiogram.py)
добавляет три узких raw method object через существующую aiogram session:
`sendRichMessage`, `editMessageText` с `rich_message` и `deleteMessage`.
Remote error text, token и HTML не попадают в исключения/отчёты.

`RecordingBot` теперь доказывает Rich lifecycle без сети. Синтетический source
компилируется в formatting/list/table/math message ровно на разрешённой границе
32 768 characters; edit использует другую compiler revision, а `finally`
удаляет returned message ID. Operations хранят только SHA-256 HTML, не content.

Guarded live-команда `make pwa-telegram-rich-live-smoke`:

- требует прежние explicit live flag и confirmation;
- принимает только owner-approved canonical test channel ID при read-only bind;
- write-step загружает только owner-only persisted binding и отклоняет иной
  destination либо destination из environment;
- повторно проверяет `@vmsh179devbot`, private channel title, canonical ID и
  send/edit/delete admin capabilities до Rich send;
- пишет owner-only report с binding/message IDs, hashes, flags и cleanup result,
  но без token или message HTML.

Разрешённый владельцем живой Rich lifecycle выполнен в уже подтверждённом
пустом test channel:

```text
VMSH_RUN_TELEGRAM_LIVE_SMOKE=1 make pwa-telegram-rich-live-smoke
run: tg-55272418570548548381
status: passed
utf8_characters: 32768
sent: true
edited: true
cleanup_attempted: true
deleted: true
```

После проверки синтетическая публикация удалена. Owner-only JSON содержит
только безопасные идентификаторы, SHA-256 и lifecycle flags; token и Rich HTML
в него не записываются. Команда сверена с официальным Bot API 10.2 contract:
[`sendRichMessage`](https://core.telegram.org/bots/api#sendrichmessage) и
[`editMessageText`](https://core.telegram.org/bots/api#editmessagetext).
Unit/E2E эту live-команду не вызывают.

## Автоматические доказательства

Герметичный focused run:

```text
pytest -q -n0 \
  pwa_tests/domain/test_content_pdf.py \
  pwa_tests/integration/test_content_pdf_smoke.py \
  pwa_tests/domain/test_telegram_rich_publisher.py \
  pwa_tests/domain/test_telegram_rich.py \
  pwa_tests/test_telegram_test_harness.py \
  pwa_tests/test_telegram_rich_capability.py
76 passed, 1 skipped
```

Skip — только явно opt-in real PDF smoke, который отдельно прошёл `1 passed`.
Fake executable tests покрывают readiness/missing, fixed argv, timeout,
non-zero, missing output, redacted error, deterministic bytes и compiler reject
до process start. Telegram tests покрывают exact limit, tamper/full-preview
reject до transport, returned IDs, send/edit/delete cleanup, raw Bot API fields,
pinned binding и content-free report.

Дополнительно:

```text
ruff check <10 affected Python files>
All checks passed!

ruff format --check <10 affected Python files>
10 files already formatted
```

## Открытые gates всего Phase 2

- real Telegram media manifest/album cases;
- визуальное сравнение трёх реальных листков PWA/Telegram/PDF;
- storage/repository/HTTP publication orchestration и orphan reconciliation;
- production/staging toolchain proof под service account в Phase 11.

Следовательно, этот derivative-adapter increment проверяем и завершён, но весь
Phase 2 остаётся открытым.
