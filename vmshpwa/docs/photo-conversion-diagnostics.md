# Диагностика конвертации фотографий

Решение от 15 ноября 2026: отказ обработки фотографии должен оставлять
сведения для разбора по request ID без сохранения исходника и раскрытия
диагностики ученику. Подтверждённый пример: GlitchTip
[VMSh issue 101](https://glitch.leaders.tech/vmsh/issues/101), HTTP 422
`written_attachment_conversion_failed`. До изменения событие frontend
содержало только code/status/requestId. Точная причина старых отказов
не восстановлена; добавление diagnostics само по себе не исправляет decoder.

[`ContentAssetConverter`](../../helpers/pwa/content/assets.py) при отказе
сохраняет в `AssetConversionError.server_diagnostics`:

- определённый по сигнатуре формат, размер и SHA-256 исходного файла;
- basename инструмента, код завершения либо timeout/OS errno;
- последние 2048 символов объединённого вывода инструмента, с удалением
  абсолютных путей, URL, управляющих символов и значений credential-полей.

Исходные байты/имя файла не включаются. `server_diagnostics` отделён от
`debug`, который используется Staff-only TikZ recovery; Student response
по-прежнему содержит только reason/capability и requestId.
Автоматически удаляемые временные файлы и лимиты converter не меняются.

[`written_submission_routes.py`](../../apps/pwa_api/written_submission_routes.py)
пишет ровно одно ERROR-событие при `AssetConversionError`. Оно содержит
request ID, reason, capability и `server_diagnostics`; stdout/stderr и
исходные байты не добавляются в публичный API. Существующая
[`LoggingIntegration`](../../helpers/config.py) пересылает событие в
GlitchTip с production release и request context. Stack locals и default PII
отключены; [`sentry_safety.py`](../../helpers/pwa/sentry_safety.py) сохраняет
диагностические ключи и удаляет request body/headers/user.

Проверки: [`test_content_assets.py`](../../pwa_tests/domain/test_content_assets.py)
проверяет оба этапа, редактирование/лимит вывода и удаление исходника;
[`test_content_http_api.py`](../../pwa_tests/integration/test_content_http_api.py)
проверяет failure/timeout, корреляцию request ID, единственное ERROR-событие,
неизменный 422 contract и отсутствие записи фото в storage.
