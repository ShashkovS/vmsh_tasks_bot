# Превью подсказок и пустые материалы — 2026-10-04

[Требования и причина](../../../vmshpwa/docs/hint-preview-empty-materials-20261004.md).
Ready hint cr-79 на gl-14 скрывался из-за missingAssets от исключённого решения.
Общий Staff preview/editor уже существовал. Исправлен HTTP role projection;
новый compiler10 исключает пустые задачи из derivatives и не требует их
condition illustrations. Source presence учитывает ответ или решение, общую
подсказку и самостоятельные пункты. Read overlay по immutable canonical AST
исправляет также старые опубликованные derivatives без перекомпиляции/записи.
Student availability/reveal исключают пустое до audit; preview скрывает кнопки.
Schema/dependencies не менялись.

## Проверки

`make pwa-check-fast PWA_E2E_MODES="content figure-layout"`:
2839 Python PASS / 7 прежних SKIP, 1032 frontend PASS, 356 Storybook PASS,
static types/lint/format/i18n PASS. Первый общий запуск дошёл до E2E:
content 2 PASS, figure-layout 3 PASS / 1 FAIL. Ошибка была только в новой
фикстуре: она ожидала ручное сопоставление, хотя upload автоматически
подтвердил соответствие и уже открыл правильное превью. После учёта обоих
разрешённых путей повторён только figure-layout: **4 Chromium PASS**,
включая реальный file upload, исключённый solution asset, редактор hint,
width/placement/hide/restore/reload/publish и Student без пустых кнопок.
Отдельные ESLint/types tools для изменённого spec PASS. Прошедшие suites
не повторялись после изменения только браузерной фикстуры.

[Полный receipt](gate-full.json), [последний браузерный receipt](e2e-final.json).
Оба режима дают 6 Chromium cases; Firefox/WebKit не запускались для этого
корректирующего инкремента. Прежний Large Classroom performance check в этом
запуске PASS; порог не менялся. Compiler characterization обновлена после
просмотра diff: AST/counts/diagnostics прежние, только compiler10 и ожидаемые
web-document hashes от additive presence metadata. Нового UI copy нет;
i18n checks PASS, extraction не требуется.

320 px light/dark hint preview осмотрены: доступны текст и инструменты рисунка,
б) и следующая задача без hint button, расположение на narrow width корректно.
[Light](hint-preview-320-light.png), [Dark](hint-preview-320-dark.png).
Production educational content не меняется: после выпуска только readonly smoke.

## Выпуск

Подготовлен [guarded manual TLF release](deploy-tlf.sh): проверенный frozen build,
production provenance, backup, остановка SQLite writers, noop schema guard,
сравнение всех product rows, сохранение credentials и shared NATS PID,
health/25 public HTTP checks, сохранение старого static/source для отката.
ВМШ — штатный webhook после разрешённого push в origin/vmshpwa.
Выпущен `cc60df33d01b29ae77476db0b43b711f79e5d370` на обоих порталах.
ВМШ webhook: frontend=true/backend=true/migrations=false,
release `cc60df33d01b-20261004115535`. Ручной TLF:
`tlfprep-20261004-hint-preview-cc60df33d01b`; **158 tables / 23862 rows идентичны**,
1593 raw Zoom receipts сохранены, credentials digest и NATS PID прежние.
Схема 0111/0112/0113 и DDL hash прежние, integrity ok; прежние 627 legacy FK
дефектов совпадают. По 25 public HTTP PASS, production provenance всех четырёх
apps, службы active, maintenance снят. Source/static rollback сохранены на TLF.
[Общий proof](production-proof.json), [ВМШ](production-vmsh.json), [TLF](production-tlf.json).

Authenticated readonly smoke gl-14: ready selector v7/cr-79 восстановлен,
PWA preview показывает текст подсказок, четыре рисунка и size/actions controls.
Учебные публикации не менялись: опубликованной остаётся v6; версия v7
доступна владельцу для просмотра/редактирования и отдельной публикации.
