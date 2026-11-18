# Итог письменной проверки — 3 октября 2026

Реализовано по [решению владельца](../../../vmshpwa/docs/written-result-precedence.md).
Выпущено на [ВМШ](https://vmsh.shashkovs.ru) штатным webhook и на
[TLF](https://prep.leaders.tech) ручным guarded cutover по разрешению владельца.
Исправление — [`dbcde4e1`](https://github.com/ShashkovS/vmsh_tasks_bot/commit/dbcde4e1fe94d10135df70053540bcdb15cd5959),
исправление прав deploy report — `56654543`. Начальный revision обоих порталов
`7259ffd0`, schema 0109; итог — schema 0110 / 82 migrations / 510 product objects.
[Машинные доказательства выпуска](production-proof.json).

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

Порядок ниже выполнен 3 октября. Итоговые доказательства — в следующем разделе.

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

## Выпуск на оба портала

Перед push свежий снимок ВМШ проверен up/down/up отдельно: все 156 product
tables, 37 540 результатов и 5 567 manual pointers сохранены. Изменились 85
текущих результатов, 22 перешли в зачёт; guard 83.192 ms. Source не менялся.
Установленный webhook script пока старее репозиторного и не содержит guard;
поэтому rehearsal выполнена вручную до push, production guard — отдельно
после autodeploy: 209.774 ms при лимите 2 s, все 7 views проходят.

ВМШ создал backups `vmsh-before-deploy-20261003192456.sqlite3` и
`vmsh-after-deploy-20261003192530.sqlite3`. Все 37 544 исходных результатов
сохранились без изменения; появилась одна настоящая automatic test оценка,
связанная с активной попыткой и result event. Она объясняет дополнительный
зачёт между snapshots. Собственно 0110 пересчитала 85 результатов и восстановила
22 зачёта. Все manual pointers сохранены; integrity ok, FK baseline прежний.
149 остальных таблиц идентичны; различия остальных семи соответствуют этой
test попытке, idempotency и обновлению одной auth session между snapshots.
Strict whole-database comparison running-service backups поэтому заменён
проверкой сохранности всех прежних строк результатов и provenance новой оценки.
Backups читались на отдельных writable temporary copies для SQLite WAL sidecars;
производственные snapshots не изменялись.

Все три указанных случая проверены в production projection: выбран прежний
более поздний Zoom-плюс 18. Webhook собрал и активировал production frontend
`dbcde4e1fe94-20261003192354`; четыре provenance artifacts без prototype/MSW.
PWA и Telegram active, maintenance снят; public smoke — **25 PASS**.

[TLF script](deploy_tlf.sh) работает под `metadata-deploy.lock`, сохраняет
credentials, NATS PID и прежний static release. Fresh backup, up/down/up
rehearsal и [сравнение данных](verify_database.py) до открытия writers проходят.
В rehearsal было 1 001 результатов; в остановленной cutover-копии — 1 002.
Все 156 product tables и все 1 002 результата сохранились, текущие зачёты
не изменились; manual pointers в этой базе отсутствуют. Guard **1.873 ms**.
Backups `20261003T192717.162838Z` / `20261003T192838.095736Z`: integrity ok,
по 1 091 Zoom receipts. PWA/Zoom/analytics active, maintenance снят;
public smoke — **25 PASS**. Record:
`/web/vmsh_tasks_bot/deploy/releases/tlfprep-20261003-written-precedence-56654543a830/`.

Первый TLF запуск остановился до maintenance/DB changes из-за владельца файла
backup report. Скрипт исправлен отдельным commit и повторён; failed record
сохранён. Credentials, ключи и product data не заменялись.
