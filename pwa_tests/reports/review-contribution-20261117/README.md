# Личный вклад учителя — 17 ноября 2026

Реализован [согласованный контракт](../../../vmshpwa/docs/review-contribution.md):
компактная строка в очереди, одиночной/серийной проверке, простыне, истории,
очном и Zoom-приёме. По нажатию — собственные итоги PWA за всё время и занятие,
разбивка по способам проверки, рубежи и дневной/недельный ритм с личным рекордом.
Отмены специально не вычитаются. Плюсы включают `+.`. Схема не менялась,
production не менялся.

## Проверки

- Типы всех приложений/пакетов, lint изменённых TS/TSX, CSS lint, форматирование
  изменённых файлов, frontend/backend i18n, scoped Ruff и `git diff --check` — PASS.
- Сервер: **8 новых domain/HTTP tests PASS**. Источники PWA и их пересечение,
  свои показатели при teacher/admin, отсутствие чужого teacher ID в запросе,
  граница плюс/полуплюс, цепочка corrections с другим автором, отсутствие
  вычитания отмен, тестовые ученики, календарные границы/год/перерывы и рубежи.
- Широкий frontend-прогон: **1157 PASS**; единственный отказ нового теста
  исправлен, после финальных изменений **8 focused tests PASS** (UI, client,
  contracts). Отдельно проверены появление после первой проверки, отсутствие
  поздравлений при загрузке, уведомление о недельном рубеже, сохранение фокуса
  и native disclosure при refetch и смене занятия, сохранение цифр при ошибке.
- Широкий Storybook-прогон: **392 PASS**; исправлена проверка синтетического
  keyboard input для native summary. Финальные **7 stories PASS**: normal,
  empty/loading/error, несколько курсов и рекорд после перерыва. Реальная
  клавиатура проверена Playwright.
- Четыре production builds и **15 E2E-прогонов Chromium PASS**, retries=0:
  5 review, 5 oral, 5 live-marking. Это 11 разных сценариев; четыре live-сценария
  намеренно повторяются с чистыми БД в двух штатных режимах. Настоящие aiohttp,
  SQLite, gateway и auth; MSW в E2E отсутствует.
- Снимки 320/390/1440 px, light/dark, CSS zoom 200%, reduced motion просмотрены.
  Блок помещается во всех размерах. Keyboard disclosure и смена фильтра не
  закрывают панель; после сохранения статистика обновляется без ожидания
  следующей работы.

Команда исходного конвейера:
`make pwa-check-fast PWA_E2E_MODES="review oral live-marking"`.
После описанных ниже baseline-отказов использованы те же этапы
`vmshpwa.scripts.check_runner.steps` с scoped formatting/lint и повтором
изменённых tests, без повторения остальных прошедших suites.
[Финальный scoped-конвейер](checks.json), [E2E phases](e2e.json),
[сводная квитанция](validation.json). `source_changed=false`.

## Ограничения общего gate

Полный gate **не объявляется зелёным**:

1. Prettier исходно отклонил 12 неизменённых файлов: `classroom-event-page.tsx`,
   `routes/questions.tsx`, `routes/review.tsx`, `student-account-batch-panel.tsx`,
   `student-results-page.tsx`, Student `student-home-page.tsx`,
   `student-notifications-page.tsx`, `student-offline-preparation.tsx`, audit
   `BACKLOG.md`/`STATUS.md`, `packages/content/src/content.css`,
   `packages/product/src/test-answer.tsx`. Эти файлы не форматировались.
2. Полный Python-прогон после разрешения локальных sockets: 3126 PASS,
   17 FAIL, 16 SKIP. Из 17 отказов один был в новом тестовом seed и исправлен;
   14 касались отсутствующих approved corpus inputs. Материалы скопированы
   в ignored локальные каталоги, их 54 fingerprint совпали с manifest;
   соответствующие проверки затем прошли. Остались две неизменённые проверки:
   `test_database_performance_guard.py::test_guard_rejects_a_correlated_full_scan_and_accepts_indexed_lookup`
   (SQLite 3.53.1 не вызывает ожидаемое исключение) и
   `test_tikz_chess_smoke.py::test_piece_scales_with_tikz_picture`
   (55 px вместо ожидаемых 62±2). Код этих подсистем не менялся.
3. Существующая простыня на 320 px имеет `scrollWidth=338` как при закрытом,
   так и при открытом блоке; сам блок не выходит за 320 px. На 390/1440 px
   ширина всей страницы совпадает с viewport. Узкое переполнение простыни
   оставлено отдельным follow-up; область — `review-sheet-page.tsx` /
   `review-sheet-card.tsx`. Это дополнительно проверяется сравнением размеров
   до/после раскрытия, а не скрывается обрезкой страницы.

## Снимки

Только синтетические ученики и учителя. Номер 9971 — изолированная E2E-фикстура,
не номер реального занятия. На снимках блок раскрыт; по умолчанию он свёрнут.

| Размер  | Светлая тема                          | Тёмная тема                          |
| ------- | ------------------------------------- | ------------------------------------ |
| 320 px  | [снимок](contribution-320-light.png)  | [снимок](contribution-320-dark.png)  |
| 390 px  | [снимок](contribution-390-light.png)  | [снимок](contribution-390-dark.png)  |
| 1440 px | [снимок](contribution-1440-light.png) | [снимок](contribution-1440-dark.png) |

[CSS zoom 200%](contribution-zoom.png).

## Production rollout

2026-11-17 выпущен на `vmshfirstvds` и `prep.leaders.tech`, source `0f7ef0f9`,
static `review-contribution-20261117`. По 25 HTTP checks PASS; schema/config
сохранены, main/analytics backups до/после проверены. [Квитанции и оставшееся
подтверждение владельца служебных каталогов](rollout/README.md).
