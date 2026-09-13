# Плотная статистика и ручной пересчёт — 2026-09-13

Требования: [lesson-statistics.md](../docs/lesson-statistics.md#dense-staff-statistics-and-manual-recalculation-2026-09-13).

## Результат

На `/staff/statistics` высота распределений увеличена до 260 px, удалены
пояснение о баллах и слово «баллы» из подписей, колонка называется «Решили».
Таблицы этой страницы используют отступы 4 × 8 px и правое выравнивание чисел.
Дробные значения и расчёт процентов сохранены. Одиночное наблюдение имеет ту
же высоту и масштаб; пустое состояние остаётся текстовым.

Администратор может запустить один шаг сложности и силы всего выбранного
курса. Выбор группы/занятия/школьника не ограничивает расчёт. Завершение обновляет
данные без сброса URL; обычное обновление статистики не запускает алгоритм.

Новая миграция 0092 хранит операции и ключи идемпотентности. HTTP проверяет
административные права и существующую CSRF-политику. Фоновый поток использует
отдельное SQLite-соединение и общий с CLI/таймером `.analytics.lock`.
Граница входных данных читается в одном snapshot с фактами и моделью. CPU-шаг
не держит транзакцию записи. Публикация модели, ряда и успешного статуса атомарна;
при аварии прерванный статус восстанавливается только после получения lock.

## Проверки

- 26 pytest: `test_statistics_recalculation.py`, `test_lesson_statistics_http.py`,
  `test_phase10_staff_statistics.py`, `test_iterative_analytics_migration.py`,
  `test_lesson_statistics.py` (domain). Администратор; запрет учителю, школьнику
  и родителю; CSRF; повтор ключа; конфликт ключа между курсами; busy без второго
  расчёта; ошибка вычислений; восстановление orphan под lock; миграция
  вперёд/назад/вперёд; атомарный rollback; совпадение ручного шага с CLI;
  исправленные старые результаты и новый результат внутри read snapshot.
- 21 проверка `pwa_tests/test_schema_inventory.py`: обновлены канонические
  schema inventory, SQL snapshot и `docs/db_structure.sql` для миграции 0092.
- 5 Vitest: `lesson-statistics.test.tsx` и `staff-statistics-client.test.ts`.
  Дробное значение/процент, новое название, одиночное наблюдение 260 px, пустые
  данные, refresh и повтор POST после истечения сессии с тем же ключом.
- Staff TypeScript, адресный ESLint, Prettier, Ruff и `git diff --check` прошли.
- Собраны все три приложения. Изолированный E2E backend, gateway и SQLite;
  production и human runtime не использовались. Браузерные тесты запускались
  через `scripts/e2e_runner.py` под общим lock.
- `e2e/statistics-recalculation.spec.ts`: Chromium, WebKit, Firefox — запуск,
  завершение, reload, сохранение URL, отсутствие POST при refresh, отсутствие
  административной кнопки у учителя. На опубликованном занятии с синтетическими
  результатами проверена фактическая высота SVG 260 px. Обе темы, 1280/390/320 px,
  отсутствие горизонтального переполнения страницы, фокус с клавиатуры.
  Масштаб 200% проверяется CSS zoom; системный browser zoom отдельно не менялся.
- Снимки проверены визуально. Широкая таблица на телефоне прокручивается внутри
  своего контейнера, не расширяя страницу. Обычные ячейки имеют высоту 28 px.

Базовые данные занятия для браузерного сценария добавляет защищённый E2E-only
`seed_e2e_statistics_recalculation.py`; это не production auth/data backdoor.
Предупреждение SymPy о deprecated gcd — существующее, тестам не мешает.

## Снимки

Финальный прогон: **6/6 passed** (по два сценария на движок).

| Движок | Desktop, светлая | 320 px, тёмная | CSS zoom 200% |
|---|---|---|---|
| Chromium | [снимок](assets/statistics-recalculation/chromium-statistics-light-1280.png) | [снимок](assets/statistics-recalculation/chromium-statistics-dark-320.png) | [снимок](assets/statistics-recalculation/chromium-statistics-200-percent.png) |
| WebKit | [снимок](assets/statistics-recalculation/webkit-statistics-light-1280.png) | [снимок](assets/statistics-recalculation/webkit-statistics-dark-320.png) | [снимок](assets/statistics-recalculation/webkit-statistics-200-percent.png) |
| Firefox | [снимок](assets/statistics-recalculation/firefox-statistics-light-1280.png) | [снимок](assets/statistics-recalculation/firefox-statistics-dark-320.png) | [снимок](assets/statistics-recalculation/firefox-statistics-200-percent.png) |

## Выпуск

Применить миграцию 0092 штатным способом перед запуском нового backend.
Обновить сборку Staff. Таймер и его настройки менять не требуется; процессу
нужны прежние права на соседний с SQLite `.analytics.lock`.

В production расчёт не запускался. Владелец разрешил commit и push доработки 13 сентября 2026 года.
Параллельные изменения, существовавшие до начала задачи, сохранены.
