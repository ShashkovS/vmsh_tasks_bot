# AI-помощник через MCP — проверка 18 октября 2026

[Контракт и инструкция](../../../vmshpwa/docs/ai-review-assistant.md).

## Итог

`make pwa-check-release PWA_E2E_MODES="authentication review submissions"` — PASS,
исходники не менялись во время проверок. [Квитанция](release-gate.json).

- 3022 Python PASS / 12 SKIP.
- 1125 frontend PASS, включая независимое применение текста/вердикта и controlled draft.
- 384 Storybook PASS, включая current/stale/empty/analysis-only AI-панель.
- 117 E2E PASS / 18 штатных SKIP в Chromium, WebKit и Firefox.
- Dependencies, format, types, JS/CSS lint, frontend/backend i18n и production builds PASS.
- Focused HTTP/MCP: 10 PASS, включая настоящий stdio-процесс, картинку, личные
  токены, конкурентные повторы, перенос/клонирование и актуальность контекста.
- Отдельный smoke: безопасный SVG 64×32 преобразован ImageMagick в PNG 64×32 (298 bytes).
- Fresh schema inventory с миграцией 0120 — 528 product objects, check PASS.

## Визуальная проверка

Все 12 снимков панели 1280/390 light/dark осмотрены: текст, независимые кнопки,
перенос кнопок на узкой ширине и сворачиваемый приватный разбор читаются во всех
трёх браузерах. CSS-анимации отключены при захвате; golden baselines не менялись.

| Браузер  | Широкий светлый                         | Широкий тёмный                         | Узкий светлый                          | Узкий тёмный                          |
| -------- | --------------------------------------- | -------------------------------------- | -------------------------------------- | ------------------------------------- |
| Chromium | [PNG](chromium/ai-panel-1280-light.png) | [PNG](chromium/ai-panel-1280-dark.png) | [PNG](chromium/ai-panel-390-light.png) | [PNG](chromium/ai-panel-390-dark.png) |
| WebKit   | [PNG](webkit/ai-panel-1280-light.png)   | [PNG](webkit/ai-panel-1280-dark.png)   | [PNG](webkit/ai-panel-390-light.png)   | [PNG](webkit/ai-panel-390-dark.png)   |
| Firefox  | [PNG](firefox/ai-panel-1280-light.png)  | [PNG](firefox/ai-panel-1280-dark.png)  | [PNG](firefox/ai-panel-390-light.png)  | [PNG](firefox/ai-panel-390-dark.png)  |

## Подготовка и повтор

Эталонные `_vmsh_examples` и `_external_pipelines`, отсутствовавшие в новом
worktree, скопированы из основного checkout как игнорируемые локальные тестовые
материалы. Настоящие Telegram/Google credentials и production state не использовались.

Первый полный gate имел 116 E2E PASS / 18 SKIP / 1 FAIL: существующий WebKit
submission-сценарий не поймал промежуточный статус «Отправляется», а error-context
и HTTP trace уже показывали принятый и зачтённый ответ (201). Тест и production
поведение отправки не менялись; в финальном повторе тот же сценарий PASS.
[Первая квитанция](first-release-gate.json).

Production-выкладка не выполнялась. Реальные LLM-вызовы в проверках отсутствуют:
модель запускается в пользовательском MCP-клиенте, а backend хранит предложения.

## Массовая выгрузка комментариев и посылок — 18 октября

Добавлены `list_review_comments(lesson_id?, problem_id?, cursor?)` и
`get_problem_submissions(problem_id, status=pending|reviewed|all, page_size?, cursor?)`.
[Контракт, семантика состояний и примеры](../../../vmshpwa/docs/ai-review-assistant.md#массовая-выгрузка-для-калибровки).

Fast gate `make pwa-check-fast PWA_E2E_MODES="review submissions"` PASS:
3028 Python / 12 SKIP, 1125 frontend, 384 Storybook, 8 Chromium E2E;
format/types/lint/i18n и сборки прошли, `source_changed=false`.
[Квитанция](bulk-exports-fast-gate.json).

Шесть новых [HTTP/SQLite-сценариев](../../integration/test_ai_review_exports_http.py)
проверяют историю после повторной сдачи, несколько учеников, точный фильтр задачи,
проверенные/непроверенные/все, прежние комментарии, 51 комментарий без потерь,
legacy-only историю и изображения, строгие входы, scope и устаревание страниц.
[Настоящий stdio MCP](../../integration/test_ai_review_http.py) вызывает оба новых
инструмента; clone/move проверены в пакетной классификации. Всего focused assistant
набор: 16 PASS. Дополнительный Ruff и `git diff --check` PASS.

Пагинация явная: полные диалоги выдаются пакетами учеников; неизвестное состояние
старых Telegram-сообщений отражено как `unknown` и включено в `all`.
Исторические ID доступны для чтения, загружать по ним новую AI-проверку нельзя.
Новых миграций, интерфейсных изменений, LLM-вызовов и production-выкладки нет.
Первый запуск остановился на форматировании двух STATUS.md; после исправления
полный fast gate завершён успешно.

## Предыдущие занятия того же уровня — 18 октября

Добавлены `get_previous_lesson_materials(lesson_id, count=3)` и
`get_lesson_material_image(lesson_id, snapshot, image_id)`.
[Семантика, реализация и примеры](../../../vmshpwa/docs/ai-review-assistant.md#предыдущие-занятия-того-же-уровня).

Fast gate `make pwa-check-fast PWA_E2E_MODES="review content"` PASS:
3039 Python / 12 SKIP, 1125 frontend, 384 Storybook, 7 Chromium E2E;
format/types/lint/i18n/build PASS, `source_changed=false`.
[Квитанция](curriculum-fast-gate.json).

11 новых [HTTP/SQLite-сценариев](../../integration/test_ai_review_curriculum_http.py)
покрывают 3/5/20 предыдущих занятий, короткую/пустую историю, границу текущего
занятия, черновики и другие уровни, 61 задачу в каждом листке без обрезания,
вступления и несопоставленные задачи, опубликованную редакцию при новом черновике,
архивный опубликованный источник рядом с приватной заменой, отсутствие материалов,
LaTeX без web AST, строгую валидацию, scope, изображения и snapshot-конфликт.
[Реальный stdio MCP](../../integration/test_ai_review_http.py) получил пакет и
настоящий image-блок через новые инструменты. Focused curriculum + assistant:
21 PASS. Ruff и `git diff --check` PASS.

Пакет возвращает все выбранные занятия целиком; `count` 1–20, порядок учебных
номеров, active/archived, тот же уровень и кружок. Публикация и порядок не
утверждают посещение или усвоение материала конкретным учеником. Новых миграций,
UI, provider-вызовов, процессов и production-выкладки нет.

## Общий выпуск с performance — 18 октября

[Release gate](combined-release-gate.json) PASS: 3083 Python / 12 SKIP,
1136 frontend, 384 Storybook, 159 E2E / 18 SKIP в трёх браузерах;
format/types/lint/i18n/build PASS, source unchanged.
Server-local migration up/down/up обеих копий production DB PASS;
168 business table hashes сохранены, новые AI-таблицы пусты, integrity ok.
[ВМШ](vmsh-rehearsal.json), [TLF](tlf-rehearsal.json),
[план штатного выпуска](../../../docs/deploy/ai-review-performance-20261018.md).
