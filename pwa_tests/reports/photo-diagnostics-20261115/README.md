# Диагностика отправки фотографий — 15 ноября 2026

По запросу владельца проверены журналы ВМШ и GlitchTip.
Request ID `94593a58ad0546c595c3511a024ecfb8` не найден в доступных server
journals или событиях GlitchTip. Read-only PostgreSQL query подтвердил
[issue 101](https://glitch.leaders.tech/vmsh/issues/101): три frontend события
`written_attachment_conversion_failed` от 4, 8 и 15 ноября. Последнее —
15 ноября 07:52:42 UTC, request `62268ab232774618b9e0095c354ae7ac`.
Их данные не содержат decoder reason/capability/stderr. Старые исходники
не сохранялись; точная причина отказов не установлена.

Добавлена [backend-only диагностика](../../../vmshpwa/docs/photo-conversion-diagnostics.md).
Новый отказ оставляет одно ERROR-событие в journal и через существующую
LoggingIntegration в GlitchTip. Корреляция — request_id; converter metadata:
source format/bytes/SHA-256, basename инструмента, exit code либо timeout/errno,
до 2048 символов redacted output. Оригинальные фото и filenames не логируются.
Публичный HTTP 422 contract и ограничения converter сохранены.

Проверки:

- 27 converter/service/HTTP/Sentry tests PASS: stderr двух этапов, timeout,
  redaction/cleanup, единственная ERROR-запись, сохранение metadata через
  настоящий Sentry EventHandler и privacy hook, отсутствие деталей в API.
- Два real-toolchain tests PASS: нормальная обработка JPEG с удалением EXIF,
  отказ на corrupt source и input выше лимита.
- Scoped Ruff и `git diff --check` PASS.
- `make pwa-check-fast PWA_E2E_MODES=submissions` остановлен до тестов из-за
  отсутствующих `vmshpwa/node_modules`. Receipt:
  `.runtime/vmshpwa/checks/20261115T094728.029203Z/summary.json`.
- Первый isolated HTTP запуск не смог bind loopback в sandbox; повтор с
  разрешённым local bind прошёл. Посторонние suites не повторялись.

Исходные версии: ВМШ c8e2a328, TLF 7a807548.
TLF получает отдельный commit только diagnostics поверх своей активной версии,
чтобы не включать несвязанные изменения personal plots/printing.
Синтетические ошибки в production GlitchTip не создаются; транспорт проверен
изолированным EventHandler test без сети. Production data/публикации не меняются.

ВМШ выпущен: `a20adbe009203bcacba08d26b755b8acce7b7f5e`.
[Квитанция](vmsh-production.json): 25 HTTP checks, реальные JPEG и corrupt-input
diagnostics PASS, GlitchTip project /2 client configured. Плавно заменены
PWA/Telegram workers при сохранении master PID. Config/schema/static/NATS
и все три unrelated tracked repairs сохранены; verified backups main/analytics.
TLF выпущен: `d2e5dddc2b0211aa86a9f93063317a10a1ab2a82`.
[Квитанция](tlf-production.json): те же проверки PASS, GlitchTip project /4
client configured. PWA workers плавно заменены, остальные функции остались
на прежней базе 7a807548. Untracked records сохранены по hash. На обоих
серверах schema/config/static/NATS сохранены, main/analytics backups прошли
integrity check, services active / maintenance off. Исходные фотографии и
отправки не менялись, синтетические события в GlitchTip не создавались.

Закрытые записи выпуска на соответствующих хостах:
`/web/vmsh_tasks_bot/deploy/releases/photo-diagnostics-20261115-a20adbe00920/`
и `/web/vmsh_tasks_bot/deploy/releases/photo-diagnostics-20261115-d2e5dddc2b02/`.
Обычный Git/SSH transport, fast-forward сохраняет unrelated edits;
schema-compatible rollback: `git reset --keep` к sourceBefore и SIGHUP workers,
без восстановления устаревшей БД. Нужен повтор проблемной отправки и свежий
request ID; старые IDs не приобретают diagnostics задним числом.
