# Импорт Zoom-событий старого сервера — 2026-10-08

Запрошено владельцем: дополнить `zoom_events` текущей БД ВМШ данными
`~/tmp/main_zoom_events.tsv`. Эндпоинт Zoom переключён владельцем на
`https://vmsh.shashkovs.ru/zoomevents`.

Подготовка: 8767 строк, 2026-09-14 — 2026-10-07; TSV SHA256
`68c0cab8289f9056315fe351e40c051121ec316f6873c0a7e6adc6326f64a20d`.
Заголовок совпадает с [текущей схемой](../../../migrations/0111.current_schema.sql).
ID 43833–52599 уникальны; полных повторов нет; `user_id` пуст у всех строк.
Пустые optional-поля переносятся в SQL NULL. Числовые и текстовые Zoom ID
сохраняются с SQLite affinity, как в
[обработчике](../../../apps/zoom_events_parser.py).

[Операционный импортёр](../import_zoom_events.py): preview без записи;
сверка SHA256; проверенный SQLite online backup перед apply; один
`BEGIN IMMEDIATE`, повторное планирование под write lock; сохранение имеющихся
строк и свободных исходных ID. Совпадения сравниваются по всем полям кроме ID
с учётом кратности: повторный запуск не добавляет строки и не теряет дубликаты
исходного архива. Очередь и результаты не воспроизводятся из исторических событий.

Репетиция PASS, 2026-10-08 11:03 по Кипру:

- Пять изолированных регрессий PASS: NULL/SQLite affinity и quoted TSV;
  конфликт ID, кратность и повтор; rollback всего пакета; неизвестный user ID;
  изменённый SHA256/существующий backup. Команда:
  `python3 -W error::ResourceWarning -m unittest discover -s docs/deploy/zoom-events-import-20261008 -p 'test_*.py' -v`.
- Проверенный SQLite online backup текущей БД:
  `/web/vmsh_tasks_bot/vmsh_tasks_bot/db/zoom-events-import-20261008/production-before-rehearsal.sqlite3`.
- На отдельной копии вставлено 8767 строк, исходные ID сохранены у всех.
  Имеющаяся диагностическая запись сохранена: итог 8768 строк. Transaction
  0.120 s. Повторный preview: 0 новых строк / 8767 уже присутствуют.
- SHA256 всех остальных 161 таблиц / 701419 строк совпали; integrity `ok`.
  627 ранее существовавших FK violations идентичны до/после; новых нет.
- TSV и импортёр переданы на сервер, checksums подтверждены. Дамп/копии БД
  в git не добавлены. Оба service PID сохранены: legacy 123859, PWA 123837.

[Обезличенный отчёт](../../../pwa_tests/reports/zoom-events-import-20261008.json)
содержит полные counts/digests и preview до/после применения. Репетиция доказала
сохранение остальных таблиц; перед применением production содержал 1 Zoom-событие.

Текущий статус: **импорт выполнен и проверен на production**. Применение
выполнил владелец 2026-10-08 в 11:11 по Кипру. Запись агенту недоступна:
ACL текущей БД/WAL дают `vmshbegetagent` только чтение;
sudoers разрешает deploy wrapper, но не запуск Python от `vmsh_tasks_bot`.
Права, сервисы и production-код не менялись ради обхода этого ограничения.

Использованный [apply.sh](apply.sh) проверяет checksums, делает свежий online
backup, затем перепланирует и импортирует под одним коротким write lock.
Новые события между preview и apply сохраняются. Запуск на ВМШ от root:

```sh
sudo -u vmsh_tasks_bot /bin/sh /web/vmsh_tasks_bot/vmsh_tasks_bot/db/zoom-events-import-20261008/apply.sh
```

Каждый запуск сохраняет новый `production-before-apply-<UTC>.sqlite3` и
`apply-<UTC>.json` в каталоге подготовки. Production apply receipt:
`apply-20261008T081103Z.json`; свежий backup
`production-before-apply-20261008T081103Z.sqlite3`, integrity `ok`.
Одна транзакция 0.0754 s: 8767 добавлены, 0 пропущены, 0 ID переназначены.

Независимая read-only проверка production завершена 2026-10-08 в 11:12 по
Кипру: все 8767 исходных ID и все поля совпадают с TSV; недостающих строк 0;
всего в `zoom_events` 8768, прежняя диагностическая запись сохранена.
Повторный preview: 8767 уже присутствуют / 0 новых. Целостность `ok`, очередь
совпадает с исходным snapshot, прежние FK violations без добавлений.
Оба сервиса active с прежними PID 123859 / 123837, NRestarts 0.
[Production verification](../../../pwa_tests/reports/zoom-events-import-production-20261008.json).
Сервисы не останавливались; для этого импорта дальнейших действий нет.
