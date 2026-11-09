# Проверка письменных работ простынёй — 11 октября 2026

Реализовано согласованное [требование](../../../vmshpwa/docs/review-sheet.md).
Основа — свежий локальный и отправленный коммит `7dd8c5a5`, включая
просмотр фотографий из `4584392b`. Владелец разрешил commit/push и выпуск на оба сервера;
[операционный record](../../../docs/deploy/review-sheet-20261011.md).
Миграции не нужны. Визуальная приёмка владельцем не заявляется.

## Поведение и покрытие

Teacher и Admin открывают `/staff/review/sheet`: занятие либо целый номер
со всеми пунктами, «Ожидающие / Все». До 300 уникальных карточек включительно
разрешено занятие; 301 оставляет только открытие по задаче. Условия всех
пунктов идут перед работами; синонимы не размножают формы.

Простыня не захватывает очередь. Чужой lease не запрещает оценку. Атомарный
snapshot CAS даёт одного победителя при одновременной отправке. После конфликта
обновляется одна карточка, сохраняются комментарий, оценка и пометки; явная
повторная отправка добавляет новую проверку. Replay не дублирует результат,
комментарий, аннотации и уведомления. Материалы оценки отделены от полной
переписки, immutable evidence сохраняется. Доступ и приватные фото ограничены
текущими grants.

Открытый состав карточек и их snapshot сохраняются при фоновых обновлениях
очереди. Черновики независимы и восстанавливаются после reload. Горячие клавиши
принадлежат активной карточке. Работы, фото и редактор загружаются по мере
прокрутки/открытия. Общая форма, реакции, перенос/клонирование и свежий
полноэкранный просмотр фото переиспользуют одиночный интерфейс. Результат и
аннотации видны Student/Family.

Тесты: [domain](../../integration/test_review_sheet.py),
[HTTP](../../integration/test_review_sheet_http.py),
[Staff](../../../vmshpwa/apps/staff/src/review-sheet-page.test.tsx),
[контракты](../../../vmshpwa/packages/contracts/src/review-sheet.test.ts),
[E2E](../../../vmshpwa/e2e/review-workspace.spec.ts).

## Проверки

На неизменных исходниках выполнен `make pwa-check-release`:

| Шаг                                                       | Результат                   |
| --------------------------------------------------------- | --------------------------- |
| Python dependencies, format, types, JS/CSS lint, оба i18n | PASS                        |
| Python (`tests pwa_tests`)                                | 2981 PASS / 12 SKIP         |
| Frontend unit                                             | 1101 PASS                   |
| Storybook interactions/a11y                               | 375 PASS                    |
| Основная E2E-матрица, три браузера                        | 399 PASS / 20 SKIP / 4 FAIL |

[Полная квитанция](full-summary.json), [E2E квитанция](full-e2e.json),
[лог](full-e2e.log). Source digest:
`342ce9ea8646cf818329729c7c2ae68b4fa55bbf41962af4eaf473dde57e4288`;
`source_changed=false`.

Новые сценарии простыни, одиночная/серийная проверка и сдача прошли во всех
трёх движках. Дополнительно на чистых фазах: 48 E2E PASS (review, submissions,
course-attendance, rich-files, support и browser-image-upload), 12 PASS
(figure-layout, whiteboard-export, worksheet-print), 9 PASS (statistics).
Staff visual: 3 PASS. [Дополнительная квитанция](additional-e2e.json) имеет
тот же source digest и `source_changed=false`.

Отдельный focused review: 12/12 PASS в Chromium/WebKit/Firefox;
[квитанция](focused-e2e.json). Проверены две сессии, reload обоих черновиков,
CAS/conflict/resend, фото/разметка, Student/Family и 390 px без overflow.

## Ограничения общего gate

Полный gate **не PASS**. Четыре исходных ошибки сохранены в [full-errors](full-errors):
Chromium `problem-release` после offline (15 ожидаемых задач против 5),
WebKit `course-attendance` (Frame load interrupted), `rich-files` (timeout
перехода в broadcasts) и `support-dialogue` (конкурирующий переход в profile).
Три WebKit-сценария прошли в отдельном прогоне без изменения кода.

Отдельная публикация: Chromium/WebKit PASS, Firefox снова 15 против 5 после
offline. [Квитанция](publication-e2e.json), [ошибка](publication-firefox-error.md).
Эта нестабильность остаётся известным follow-up общего release gate.

Student «Сейчас»: 3 visual FAIL. Diff показывает существующие подсказки
«Сейчас у вас онлайн-режим. Поменять» в блоках очных занятий; геометрия страницы
стала выше. Компонент изменён базовым коммитом `a7bccbc1` от 1 октября,
снимки последний раз обновлены в `26e2f7ee`. [Diff и actual/expected](visual-diffs)
просмотрены; существующие baselines не изменены.

## Снимки простыни

Сохранено 18 снимков: полный экран, карточка конфликта и 390 px, light/dark,
три движка. Представительные полные страницы просмотрены:
[Chromium desktop light](screenshots/chromium/sheet-page-light.png),
[Chromium mobile light](screenshots/chromium/sheet-mobile-light.png),
[WebKit mobile dark](screenshots/webkit/sheet-mobile-dark.png),
[Firefox mobile dark](screenshots/firefox/sheet-mobile-dark.png).

## Окружение

Только изолированные E2E API/gateway, SQLite/media/NATS. Production,
Telegram polling и Google credentials не использовались. Для Python corpus
подготовлены отдельные локальные копии ignored `_vmsh_examples` и
`_external_pipelines`; системные `.DS_Store` в копиях исключены.

## Production-выпуск

Владелец разрешил выпуск после сообщения об ограничениях gate. `08d4926d`
интегрирован в основную ветку `vmshpwa`, запушен и развёрнут на обоих серверах.
По 25 HTTP checks и 116 Staff asset hashes PASS, все четыре HTML/provenance
совпадают, службы active, maintenance off, backups integrity ok.
[Операционный record](../../../docs/deploy/review-sheet-20261011.md),
[proof](production-proof.json). Production browser acceptance под Staff-сессией
не заявляется; общий gate не стал зелёным от production smoke.
