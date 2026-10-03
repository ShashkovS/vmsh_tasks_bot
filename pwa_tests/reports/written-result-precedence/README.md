# Итог письменной проверки — 3 октября 2026

Реализовано по [решению владельца](../../../vmshpwa/docs/written-result-precedence.md).
Production не менялся; выпуск подготовлен, но не выполнялся.

Владелец затем разрешил commit/push, автоматический выпуск на ВМШ и ручной
выпуск на TLF. Выпуск начат: исходный revision обоих порталов `7259ffd0`,
schema head 0109. [Guarded TLF script](deploy_tlf.sh) выполняет backend-only
cutover под общим deploy lock, fresh backup, up/down/up rehearsal и
[проверку сохранности данных](verify_database.py) до возврата writers.
Статический frontend не меняется. Итог выпуска будет записан после smoke.

## Реализация

- [0110 и rollback](../../../migrations/0110.pwa_written_result_precedence.sql)
  сохраняют колонки `effective_results` и исходную строку выбранного результата.
  Последние письменная и действующая ручная оценки всей группы синонимов
  сравниваются по ID и `verdicts.val`; старый ручной указатель не сбрасывается.
- [Список задач](../../../db_methods/pwa/content.py),
  [прогресс](../../../db_methods/pwa/progress.py),
  [Zoom/очная таблица](../../../db_methods/pwa/live_marking.py),
  [Telegram](../../../db_methods/db_results.py) и
  [текущие результаты архива](../../../db_methods/pwa/student_results.py)
  читают общую проекцию. Telegram переносит выбранную оценку на каждый синоним
  до фильтрации по уровню. Отчёты Telegram используют текущий зачёт.
- [Письменное завершение](../../../db_methods/pwa/reviews.py),
  [перепроверка](../../../models/pwa/review_corrections.py),
  [Telegram teacher handlers](../../../handlers/teacher_handlers.py) и
  [прежний oral API](../../../models/pwa/oral_results.py)
  больше не обнуляют прежние письменные/устные оценки для обхода исторического
  максимума. Новая строка становится текущей, прежние значения остаются историей.
- Версии соседних синонимов повышаются при insert/update/delete и undo.
  Автоматические тестовые ответы сохраняют правила 0091/0095. HTTP-контракты
  и интерфейс проверки не менялись; календарь читает raw ledger отдельно.

## Проверки

[Новые acceptance tests](../../integration/test_written_result_precedence.py)
проверяют 121 пару всех 11 значений `verdicts`, строгие сравнения и равенства,
последний действующий manual вместо исторического максимума, более новый manual
всей шкалы, порядок ID при обратном порядке timestamps, повышение/понижение,
разных учителей/учеников, modern и legacy синонимы, undo, CAS, replay,
Student/Family, Telegram, архив, календарь и up/down/up.

Команды и результаты (runtime logs в `.runtime/written-precedence-*.log`):

- `.venv/bin/python -m pytest -q -n4 pwa_tests tests`: **2822 passed, 7 skipped**,
  три failures новых/исторических fixtures исправлены и повторно проверены:
  допустимый письменный плюс — 17, новый browser seed inventory, исключение
  0110 из намеренно неполной no-course schema lag fixture.
- Итоговый прогон review repository/HTTP/series, written precedence, review
  notifications, live marking, archive и всего `tests`: **352 passed, 1 skipped**.
  До финальной правки сохранения истории прошли также 319 checks
  progress/Family/schema/legacy; единственный добавленный CAS fixture исправлен
  и повторён: **3 passed**. Schema artifacts актуальны: **510 объектов**.
- Дополнительно oral/live-marking regression: **19 passed**, включая новый
  [сценарий сохранения manual history](../../integration/test_phase7_oral_results.py).
  Legacy oral API также добавляет новый минус без изменения прежнего плюса.
- Vitest course/Family clients, realtime provider/client, written clients:
  **48 passed**. Tools TypeScript и scoped ESLint/Prettier/Ruff проходят.
- `make pwa-e2e-review` собрал четыре production bundles. Итоговый запуск через
  `exclusive_e2e_run`/`run_commands` с `playwright test e2e/review-workspace.spec.ts
--retries 0`: **9 passed / 51.5 s**, Chromium/WebKit/Firefox.
  [Новый сценарий](../../../vmshpwa/e2e/review-workspace.spec.ts) проверяет
  Student/Family без reload, после reload, письменное понижение во время offline,
  reconnect, повторное повышение, новый Zoom-минус и undo до письменного плюса.
  Прежние series/review/annotation/reaction сценарии также проходят.

Браузерные fixtures приведены к существующему контракту: уникальные IDs,
`answerType=null` для written, отдельный pending статус до complete.
Ошибки тестовых селекторов исправлены; retries и visual baselines не ослаблялись.
Во время остановки промежуточного прогона оставшиеся два E2E-процесса на
8380/5380 были определены и остановлены перед окончательным прогоном.

## Репетиция на рабочем снимке

Использован существующий серверный backup ВМШ
`/web/vmsh_tasks_bot/backups/vmsh-after-deploy-20261003141412.sqlite3`.
Он прочитан и скопирован в `.runtime/written-precedence/production-before.sqlite3`;
отдельная копия `rehearsal-final.sqlite3` мигрирована локально.
Исходный файл проверен SHA-256 до/после и не изменился.

[Скрипт](rehearse.py) требует новый путь копии, открывает source read-only и
проверяет каждый шаг up/down/up. [Машинный отчёт](rehearsal.json):

- integrity `ok`; 36 643 строки `results`, 5 567 manual pointers сохранены;
- 156 остальных product tables совпадают по counts и SHA-256;
- прежние 627 orphan FK references `kv_logins` сохранились, новых нарушений нет;
- 81 текущий результат изменился, 20 перешли в зачёт;
- query guard: up **185.788 ms**, down **48.659 ms**, up **143.247 ms**;
  лимит 2 s, все планы views проверены на correlated full scans.

Все три примера уже исправлены новым Zoom-плюсом в этом снимке:

| Ученик            | Задача | Ручной минус | Письменный плюс | Последующий Zoom-плюс |
| ----------------- | ------ | ------------ | --------------- | --------------------- |
| Баймиева Юстина   | 2п.10б | 14516        | 20403           | 27670, 26 сентября    |
| Демьяненков Назар | 2п.10а | 13545        | 14055           | 28969, 27 сентября    |
| Демьяненков Назар | 2п.11а | 13554        | 16846           | 28971, 27 сентября    |

Зависание исторически подтверждено, но эти записи не входят в 20 исправляемых
сейчас зачётов: их более поздний Zoom-плюс остаётся выбранным.

## Подготовка выпуска

1. Выпустить backend и migration 0110 вместе по действующему
   [production checklist](../../../vmshpwa/docs/production-rollout-checklist.md),
   с остановкой приёма новых writes и завершением текущих транзакций.
2. Сделать свежий согласованный SQLite backup перед применением, проверить
   integrity и сохранить отдельно от release. Сегодняшний backup и локальная
   неизменённая копия уже имеются; перед фактическим cutover нужен свежий снимок.
3. Повторить `rehearse.py` на новой копии свежего backup. Не запускать тестовый
   runtime на рабочей БД. Репетиция копии не включает production credentials.
4. Применить head через существующий migration/runtime lifecycle, проверить
   schema inventory 510, performance guard, pointers/history fingerprints,
   health и выбранные статусы. Перезапустить все backend adapters с новым кодом.
5. Проверить Student/Family list/progress, письменный thread, Zoom и Telegram
   на одних задачах; сопоставить изменённые результаты с новым правилом.
   Фиктивные результаты и повторные плюсики не нужны.
6. SQL rollback проверен. Если после cutover уже появились новые перепроверки,
   прежняя проекция может вновь выбрать исторический письменный максимум:
   откат требует отдельного контроля последних вердиктов. Сохранять новые
   записи и исправлять вперёд; backup восстанавливать только по принятому
   протоколу восстановления, с учётом всех последующих writes.

Воспроизводимая команда репетиции (новый `--copy` обязателен):

```sh
VMSH_RUNTIME_PROFILE=pwa-e2e VMSH_INSTANCE=e2e \
VMSH_DB_FILENAME=db/vmshpwa_e2e.sqlite3 VMSH_MEDIA_ROOT=.runtime/vmshpwa/e2e \
VMSH_NATS_SERVER= .venv/bin/python -m pwa_tests.reports.written-result-precedence.rehearse \
  --snapshot .runtime/written-precedence/production-before.sqlite3 \
  --copy .runtime/written-precedence/rehearsal-next.sqlite3 \
  --report .runtime/written-precedence/rehearsal-next.json
```
