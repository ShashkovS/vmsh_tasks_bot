# Публикация и диагностика материалов — 4 октября 2026

[Требования, причины и компоненты](../../../vmshpwa/docs/content-recovery-20261004.md).

`make pwa-check-fast PWA_E2E_MODES="content figure-layout"`, с продолжением
после sandbox/socket и исправлений тестового bookkeeping: **2823 Python PASS /
7 SKIP, 1028 frontend, 356 Storybook, 6 Chromium E2E**. Прошедшие неизменённые
static steps сохранены; после изменения миграции повторён backend, затем
выполнены ещё не запускавшиеся frontend/Storybook/E2E.
[Сводка](gate-summary.json), [static](gate-static.json),
[продолжение](gate-resumed.json), [E2E](gate-e2e.json).
Firefox/WebKit не запускались; владелец затем расширил выпуск на TLF.

Реальный E2E публикует первое условие через расписание, читает его как Student,
заменяет второй версией и откатывает к первой. Storybook проверяет серверную
причину и request ID под «Подтвердить», отсутствие ложного refetch,
два видимых блока с одним live announcement.

![Ошибка под подтверждением — синтетический Storybook-сценарий](confirmation-error.jpg)

[Проверка двух предоставленных CP1251 файлов](source-probe.json): в условиях
и подсказках нет ошибок; отсутствующие `cube-scan1-sol` и `cubes-sol` нужны
только для решения, с прежними точными координатами 125:30 / 128:30.
Descriptors остальных рисунков в этом parser probe синтетические; реальные
upload/inventory/attach/compile проверены интеграционными HTTP-тестами.
Исходные файлы не изменялись.

[Серверная репетиция](migration-rehearsal.json) использует согласованную
временную копию, которая удаляется после проверки. Все 606 819 строк 158
таблиц сохранились; изменился только DDL `lesson_publications`. Прежние 627
legacy FK-ошибок остались ровно прежними, новых нет; integrity `ok`.
В копии проверены обе terminal transitions настоящего `gl-13` с сохранением
аудитных триггеров и происхождения; изменения probe отменены savepoint.
Production row data не выгружались. [Скрипт](rehearse-vmsh.py).

[Rollback source](rollback-source.json): `43b7d2f`,
`codex/content-recovery-rollback-20261004`. Сохраняет 0112 и актуальные schema
artifacts поверх предыдущего `b6476a52`. Проверены startup guard и замена
активированной публикации прежним backend. Миграция отказывает в обратном
DDL при наличии terminal schedule history; её нельзя удалять для отката кода.

Владелец явно разрешил push в существующий GitHub origin, автодеплой ВМШ
и ручной деплой `prep.leaders.tech`; первоначальный отказ auto-review снят
после этого разрешения. `9a14443f` отправлен в основную deployment-ветку
`origin/vmshpwa`, rollback `43b7d2f` — в отдельную ветку. Выпуск обоих
порталов завершён с backup, rehearsal и read-only smoke. Учебные материалы пользователь
публикует сам; `gl-14` hint revision 6 и старая invalid `cr-75` не меняются
агентом.

## Production — 4 октября 2026

[Общий proof](production-proof.json), [ВМШ](production-vmsh.json),
[TLF](production-tlf.json), [read-only verifier](production-probe.py),
[ручной TLF deploy](deploy-tlf.sh). На ВМШ сработал штатный webhook.
Код `9a14443f` и migration 0112 действуют на обоих порталах.

ВМШ release `9a14443fbc23-20261004093414`, backups
`vmsh-before-deploy-20261004093528.sqlite3` /
`vmsh-after-deploy-20261004093549.sqlite3`: 155 product tables идентичны.
Между backups PWA уже открыл writers: в 09:35:50 UTC прошёл один
`session.rotated`. Старые auth events/consumed secrets сохранились; изменились
ровно четыре поля одной сессии и добавились два audit/history rows, что точно
соответствует `db_methods/pwa/auth.py:rotate_refresh_secret`. Credentials,
session identifiers и row payloads остались на сервере. Все опубликованные
и scheduled материалы `gl-13`/`gl-14` совпадают с pre-deploy state.

TLF release `tlfprep-20261004-content-recovery-9a14443fbc23`, backups
`20261004T093736.871407Z` / `20261004T093804.117638Z`: все 158 product tables /
18 786 строк идентичны, включая 1421 raw Zoom receipt. Rehearsal 0112 —
0,149 с, только `lesson_publications` DDL; прежние FK-дефекты сохранены,
новых нет. Credentials и NATS PID сохранены, PWA/Zoom/analytics активны.
База для отката не восстанавливается после открытия writers; code rollback
сохраняет 0112 и её terminal history.

Оба портала: schema current, integrity `ok`, четыре production bundles без
prototype/MSW, по 25 публичных HTTP checks PASS, maintenance снят. Сохранены
708 assets предыдущего ВМШ release и 588 TLF. В браузере проверены
authenticated `gl-13`/`gl-14` и английская TLF Staff overview. Проверка
публикации с заменой — изолированный E2E; production-проверки read-only.
