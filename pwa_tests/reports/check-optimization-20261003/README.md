# Оптимизация цикла проверок — 3 октября 2026

Следующий шаг выполнен 2026-10-04: [82 миграции → одна исходная схема,
исторические migration tests удалены](../../../vmshpwa/docs/schema-baseline-20261004.md).
Ниже сохранены исходные измерения предыдущего этапа.

Запрос владельца: измерить исходное время и результат; исключить повторные
сборки, миграции и старты backend; небольшие изменения проверять в Chromium.
Полная матрица остаётся отдельным режимом. Production этим изменением не
затрагивается.

## Замеры до изменений

Исходный commit: `dc808173`. Один тяжёлый набор за раз; Python — 4 workers,
Vitest — 2; Node 26.9.0, pnpm 11.15.1, frozen Python dependencies.
Исходные логи и JSON времени: `.runtime/check-optimization-20261003/`.

| Набор                                                       | Время, включая запуск | Результат                          |
| ----------------------------------------------------------- | --------------------: | ---------------------------------- |
| Python `tests pwa_tests`, 4 workers                         |             693.768 с | 2822 pass, 7 fail, 7 skip          |
| Frontend unit, 2 workers                                    |             131.574 с | 1024 pass / 202 файла              |
| Storybook                                                   |             122.134 с | 352 pass / 74 файла                |
| Content + review + submissions, Chromium, отдельные запуски |              98.028 с | 8 pass; 3 build/backend/seed цикла |

Падения Python относятся к import-time Prometheus setup: при совместном
запуске legacy handlers импортируют клиент раньше настройки multiprocess
каталога в `pwa_tests/conftest.py`. Исправление переносит настройку в корневой
`conftest.py`, до импортов обоих адаптеров. Исходный результат сохранён,
семь assertions не удаляются и не ослабляются.

Сравниваем одинаковые команды/сценарии и отдельно учитываем холодный и
повторный запуск. Сокращение browser coverage показываем отдельно от
ускорения одинакового Chromium-набора.

## План и приоритет

1. Python: измерить полный набор и длительности setup; обычные DB fixtures
   клонируют один шаблон текущей схемы. Lifecycle/migration tests продолжают
   применять настоящие migrations. Данные каждого теста остаются независимыми.
2. E2E: content-addressed кеш проверенной E2E-сборки; единый seed-процесс и
   неизменяемые DB/media snapshots. Изменение миграций, seed, fixtures,
   dependencies или build environment инвалидирует соответствующий кеш.
3. Совместимые focused modes объединяются в один Playwright-процесс с одним
   настоящим aiohttp/gateway. Разрушительные fixture families получают свежую
   копию seed. Cross-process и SQLite lifecycle locks сохраняются.
4. Один последовательный fast/release pipeline без повторного Python-набора,
   с фиксированными toolchain/workers и измерением каждого шага. Fast —
   Chromium; release — три браузера.
5. Чистые contract unit tests не загружают DOM/переводы; повторный ESLint
   использует content cache. Сначала внедряются пункты с наибольшим измеренным
   вкладом, затем проверяется полный набор и сравниваются результаты.

## Gates и результаты

Единый `fast` gate с `content review submissions` — **PASS, 286.015 с**
(4 мин 46 с), `source_changed=false`. Один Python набор, один frontend,
один Storybook, одна E2E-сборка-проверка и один backend/gateway для восьми
выбранных сценариев. Все десять шагов PASS.

| Набор                    |            До |                               После | Результат после                  |
| ------------------------ | ------------: | ----------------------------------: | -------------------------------- |
| Python, 4 workers        |     693.768 с |                            79.489 с | 2846 pass, 7 прежних skip        |
| Frontend unit, 2 workers |     131.574 с |                            50.950 с | 1028 pass / 203 файла            |
| Storybook                |     122.134 с |                            62.227 с | 355 pass / 74 файла              |
| Те же 8 Chromium E2E     |      98.028 с |       46.522 с cold / 41.110 с warm | 8 pass, один backend вместо трёх |
| JS lint                  |     111.697 с |        32.537 с cold / 1.403 с warm | PASS                             |
| Types                    | исходный FAIL | 21.224 с cold / 7.831 с incremental | PASS                             |

Cold E2E принудительно пересоздал build и seed. Mixed из полного gate
использовал verified build cache, но новый seed key пересоздал snapshot за
1.072 с. Чистый warm замер — **41.110 с**, build hit за 0.143 с, чистые DB/media
восстановлены за 0.037 с. Все восемь сценариев исполнились повторно и прошли. Последние два успешных полных
Python прогона — 96.597 и 79.489 с; это диапазон 7.2–8.7× от исходного.

Исходный typecheck упал из-за временного незакомиченного теста параллельной
работы (`Promise.withResolvers` при ES2022); этот тест его автор исправил.
Поэтому 68.296 с того FAIL не используем как доказательство ускорения типов.
Параллельная UI-правка добавила 4 unit tests и 3 stories между замерами;
они входят в итоговый зелёный gate. Storybook напрямую не переработан:
сокращение времени этого шага нельзя приписать отдельному изменению runner.
Замеры однократные на общей рабочей машине, с разным состоянием tool caches;
это сравнение практического цикла, не статистический microbenchmark.

Первый after Python прогон выявил старую утечку `PROD` и перезагруженного
Config из `tests/test_config.py`. Исторические assertions сохранены, проверка
реальных credentials вынесена в отдельный process. Первый gate после разделения
Vitest окружений выявил browser-dependent service-availability test: он явно
сохраняет jsdom; ни один assertion не ослаблен. Эти диагностические FAIL логи
сохранены, но не выдаются за успешные after gates.

Дополнительно проверены все **139 уникальных Chromium-сценариев** по фазам.
Исходный полный run: 132 PASS и один FAIL в service-worker handover. При активации
из другой вкладки generation probe иногда теряет ответ во время смены controller;
`expect.poll` обрывался исключением вместо следующей проверки readiness.
Исправлен только этот transient case: polling продолжает ждать точную generation
и nonce; timeout и retries не увеличены. Весь runtime-isolation набор после правки
— **75 PASS** в Chromium/WebKit/Firefox (25 на engine), 82.466 с, retries 0.
Оставшиеся figure/statistics/visual фазы — **6 PASS**, 45.897 с. Уже пройденные
остальные 108 main cases не запускались заново; 24 runtime cases повторились как
часть проверки исправленного runtime spec. Visual baselines не обновлялись.
Общую сумму этих диагностических запусков не выдаём за один зелёный full run.

В финальном snapshot restore исправлена уборка собственных временных WAL/SHM
файлов; независимый cache/lock gate после этой правки зелёный. Receipt guard
учитывает незакомиченные code/config files, но исключает test reports из source
hash: новые результаты не являются изменением тестируемого кода. Добавлена
read-only Python dependency проверка `uv sync --frozen --check` перед suites;
она не устанавливает пакеты. Эти финальные guard/cleanup правки проверены
отдельным gate, **28 PASS**; замер 286.015 с сделан перед добавлением 26 ms
dependency preflight и финальных guard/cleanup правок, не повторяем все suites
ради изменения отчётности. Types/lint/format после E2E-правки PASS.
Production rollout и SSH/backup/maintenance время в этом инкременте не измерялись; ускорение именно deployment не заявляется.

## Использование

```sh
make pwa-check-fast PWA_E2E_MODES="content review submissions"
make pwa-check-fast              # весь Chromium E2E
make pwa-check-release           # полный E2E в трёх браузерах
```

При изменении dependencies отдельно обновить установленное окружение по
lockfile; обычный gate проверяет соответствие и ничего не переустанавливает. Read-only Python проверка:
`UV_CACHE_DIR=.runtime/uv-cache uv sync --frozen --check` (135 packages,
26 ms, no changes в этом прогоне). Подробности profiles, cache keys,
`--fresh-build --fresh-seed` и выбор modes:
[testing strategy](../../../vmshpwa/docs/testing-strategy.md).

Полные исходные логи/JSON: `.runtime/check-optimization-20261003/`; успешный
pipeline: `fast-final/summary.json`, E2E phase/build/seed timings: `fast-final/e2e.json`.
Проверки кешей: `pwa_tests/test_check_optimization.py`,
`pwa_tests/test_sqlite_template.py`, `pwa_tests/test_e2e_runner.py`
— 28 PASS; дополнительно legacy/domain/API/metrics gates и весь Python набор.

План и результаты связаны с [phase 0](../../../vmshpwa/dev/development-plan/04-phase-0-baseline.md),
[development status](../../../vmshpwa/dev/development-plan/STATUS.md) и
[rollout checklist](../../../vmshpwa/docs/production-rollout-checklist.md).

## Наибольший эффект и границы

Основной измеренный вклад — независимые копии текущей схемы вместо тысяч
повторных migration bootstrap: Python экономит около **10 минут** на одном
наборе, ещё больше при устранении повторного `pwa-python-test`. Перенос pure
contracts в Node экономит примерно **81 секунду** frontend; batching трёх
focused E2E экономит **51–57 секунд** при той же Chromium coverage. Сокращение
матрицы для малых правок — отдельное решение владельца, его эффект не подмешан
в эти сравнения.

Production-миграции не удаляются: шаблон сохраняет не только DDL, но и seed rows,
yoyo IDs/hashes и WAL. Новая migration автоматически создаёт новый шаблон.
Схлопывание production-истории не требуется для полученного ускорения и
потребовало бы отдельного согласования существующих yoyo histories.

Все выбранные тесты выполняются каждый раз. Новый gate не кеширует PASS,
не подменяет реальный backend, не ослабляет assertions, performance deadlines
или screenshot thresholds. `make python-test pwa-test` также больше не дублирует
PWA Python: dry-run показывает один legacy и один PWA invocation. Замеры
доступны в [measurements.json](measurements.json); исходные логи локально в ignored
runtime каталоге. Product-правки параллельного UI-инкремента сохранены.
