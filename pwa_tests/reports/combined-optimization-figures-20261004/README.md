# Общий выпуск оптимизации и исправления рисунков — 4 октября 2026

Владелец разрешил единый fast gate и выпуск на оба production вместе
исправления live-превью рисунков, оптимизации проверок и baseline 0111.

## План

1. Проверить состав текущих изменений и готовность обоих production.
2. Один `make pwa-check-fast PWA_E2E_MODES="figure-layout review"`:
   полный Python/frontend/Storybook/types/lint/i18n, нужные Chromium E2E.
3. Зафиксировать протестированный код, опубликовать в `origin/vmshpwa`.
4. ВМШ: штатный guarded webhook; TLF: reviewed script под deploy lock,
   build/provenance, verified backups, репетиция принятия baseline,
   writers stop, неизменность product rows, restart и atomic static activation.
5. Оба портала: schema 0111/current, HTTP smoke, services, maintenance cleared,
   retained immutable assets, before/after database checks и итоговые времена.

База baseline не меняет product DDL/rows. Новые БД создаются из одной миграции;
production 0110 принимают её через yoyo mark. Current media inventory contract
восстановлен в `test_media_inventory.py`: он проверяет текущую БД, не старую
цепочку. Исторические тесты/SQL повторно не запускаются.

## Статус

Выпущено на оба production: код `b5a7a6b3`, baseline `0111.current_schema`.
[Production proof](production-proof.json): ВМШ — все 597 611 строк в 158
product tables идентичны между pre/post backups; TLF — все 16 054 строки
в 158 tables идентичны при остановленных writers, 1091 Zoom receipts
сохранены. На обоих servers прежние 82 yoyo entries сохранены и добавлена
одна отметка baseline. DDL fingerprint одинаковый, 510 объектов.
Verified static/provenance production всех восьми app artifacts, MSW/prototype
выключены; сохранены 7028 старых ВМШ immutable files и все 588 assets прежнего
TLF release. PWA, Telegram ВМШ, Zoom TLF, analytics active; maintenance снят.
По 25 public HTTP PASS на портал, TLF config и NATS PID не менялись.
Полные production row data остаются на серверах.

TLF: backup/build/rehearsal/cutover/HTTP/backup — **101,822 с**. Frontend
install/build — 20 с, остановка PWA — 75 с: workers завершились за 1 с,
master через 30 с, два дочерних `ThreadPoolExecu` остались до systemd
final-sigterm timeout 45 с. Это отдельный измеренный lifecycle follow-up;
в этом выпуске настройки shutdown не изменялись. ВМШ: от начала frontend
build до записи deployed revision — **110,052 с**; fetch/install перед build
в эту цифру не включены. Эти deploy времена не сравниваются с отсутствующим
исходным end-to-end измерением.

Локальные проверки:
Полный Python: 2782 PASS / 1 FAIL / 7 SKIP за 40,419 с. Единственное падение
в тесте activity связано с совпадением сегодняшнего дня с датой фикстуры:
manual event теперь фиксирован на 3 октября, written event — 4 октября.
Все assertions сохранены; весь затронутый файл повторён — 140 PASS за 4,66 с.
Итого 2783 уникальных Python PASS / 7 прежних SKIP, без повторения уже
прошедших suites. Production code после полного Python не менялся.

Frontend: 1028 PASS / 46,925 с; Storybook: 355 PASS / 58,718 с;
Chromium figure-layout + print + whiteboard + review: 7 PASS / 37,168 с.
Types/lint/format/i18n PASS, verified E2E build и seed cache переиспользованы,
исходники во время проверок не изменялись. Суммарное время автоматических
проверок с повтором одного Python файла — **209,928 с (3 мин 30 с)**;
это сумма исполнения, без времени диагностики и подготовки deployment.

[Receipt](gate-summary.json), [E2E phases](e2e.json),
[reviewed TLF deploy script](deploy-tlf.sh). Временные сырые логи:
`.runtime/combined-optimization-figures-20261004/`.

## Компоненты

- [Live-превью](../../../vmshpwa/docs/figure-layout.md#исправление-превью-подсказок--3-октября-2026).
- [Ускорение gate](../check-optimization-20261003/README.md).
- [Текущая baseline](../schema-baseline-20261004/README.md).
