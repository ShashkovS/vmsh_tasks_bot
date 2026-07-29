# Phase 7: окна устной сдачи

## Проверяемый результат

- Admin может создать и изменить несколько окон устной сдачи для конкретного
  группового занятия; одинаковые номера окон в одном занятии запрещены.
- Teacher получает `403` на изменение конфигурации.
- Student в online-режиме видит время, подпись и состояние окна, но не получает
  URL и код подключения в общем ответе.
- URL и код возвращаются отдельным `no-store` запросом только для открытого окна
  и только при доступе Student к группе занятия.
- При очном режиме Student не получает конфигурацию online-приёма.
- Обновление требует актуальный `If-Match`; устаревшая версия возвращает `409`.

Этот срез не создаёт очередь устного приёма и отдельный журнал результатов.

## Реализация

- `migrations/0070.pwa_oral_windows.sql` и rollback;
- `db_methods/pwa/oral_windows.py` — только прямые SQLite-запросы;
- `models/pwa/oral_windows.py` — проверка времени, URL и состояния окна;
- `apps/pwa_api/oral_window_routes.py` — права, HTTP-ошибки и русские тексты;
- `pwa_tests/integration/test_phase7_oral_windows.py`.

## Автоматические доказательства

- точный цикл миграции `up → down → up` и `PRAGMA integrity_check`;
- admin/teacher permissions, конфликт номера и optimistic conflict;
- отсутствие секрета подключения в Student list;
- отдельное раскрытие подключения и проверка online-режима;
- 43 соседних Phase-7/API теста прошли вместе с новым сценарием;
- `pwa_tests/test_schema_inventory.py` и canonical schema artifacts обновлены
  на migration head.
