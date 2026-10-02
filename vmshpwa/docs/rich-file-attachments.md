# Файлы в Rich Markdown

## Требование и границы

Новости, рассылки/баннеры и блоки до/после задач позволяют прикрепить файл
до 50 МиБ. Разрешены PDF, DOC/DOCX, XLS/XLSX, PPT/PPTX, ODT/ODS/ODP,
TXT/CSV, ZIP/7Z/RAR. После загрузки редактор вставляет обычную Markdown-ссылку
с именем файла. Загрузка не сохраняет и не публикует текст автоматически.

Файл доступен всем, у кого есть постоянная ссылка. Скрытие публикации или
удаление ссылки не удаляет объект. Карточки, автоматическая offline-загрузка
и физическая очистка объектов не входят в этот инкремент.

## Реализация

- Политика имён, MIME и URL:
  [`models/pwa/rich_files.py`](../../models/pwa/rich_files.py).
- Сохранение неизменённых байтов в существующий ObjectStorage:
  [`helpers/pwa/rich_files.py`](../../helpers/pwa/rich_files.py).
- [`apps/pwa_api/rich_file_routes.py`](../../apps/pwa_api/rich_file_routes.py): admin-only
  `POST /staff/api/v1/rich-media/files/uploads`, group-scoped
  `POST /staff/api/v1/group-lessons/{id}/blocks/files/uploads`
  с `content.manage`, публичный filesystem GET
  `/pwa-rich-files/{sha256}/{filename}`.
- Контракты и транспорт:
  [`staffRichFileUploadResponseSchema`](../packages/contracts/src/rich-media.ts),
  [`StaffRichMediaClient.uploadFile`](../packages/app-shell/src/rich-media-client.ts),
  [`LessonBlockClient.uploadFile`](../packages/app-shell/src/lesson-block-client.ts),
  общий [`uploadRichFile`](../packages/app-shell/src/rich-file-upload.ts).
- Авторинг: общий [`StaffFileUpload`](../apps/staff/src/staff-file-upload.tsx),
  [`RichMarkdownEditor`](../apps/staff/src/rich-markdown-editor.tsx),
  [`StaffLocalNewsComposer`](../apps/staff/src/staff-local-news-composer.tsx),
  [`StaffGroupBannersPage`](../apps/staff/src/staff-group-banners-page.tsx),
  [`StaffLessonBlockEditor`](../apps/staff/src/staff-lesson-block-editor.tsx).

Ключ содержит SHA-256 байтов и безопасное имя. MIME определяется расширением
на сервере, архивы не распаковываются. S3 возвращает прямой HTTPS URL;
filesystem — строго ограниченный относительный URL. Изображения сохраняют
прежнюю HTTPS-политику. Ссылки используют существующие Markdown/AST/revisions
без миграции SQLite.

Имя — NFC basename без разделителей пути и управляющих символов, до 255 байт
UTF-8; расширение сохраняется. Публичный ключ:
`rich-files/sha256/{sha256[0:2]}/{sha256[2:4]}/{sha256}/{filename}`.
Повторная загрузка одинаковых байтов с тем же именем возвращает тот же URL.

API принимает одну multipart-часть `file`. Ответ HTTP 201:

```json
{
  "schemaVersion": 1,
  "file": {
    "url": "/pwa-rich-files/<sha256>/document.pdf",
    "filename": "document.pdf",
    "mimeType": "application/pdf",
    "byteSize": 1024
  },
  "requestId": "<request-id>"
}
```

Невалидный файл/лишняя часть: HTTP 422 `rich_file_invalid`; превышение 50 МиБ:
HTTP 413 `payload_too_large`; недоступное storage: HTTP 503
`rich_files_unavailable`. Права проверяются до чтения multipart и записи объекта.
Upload блоков не требует ETag: он не изменяет черновик или публикацию.

Подпись экранируется через
[`fileAttachmentMarkdown`](../apps/staff/src/file-attachment-markdown.ts).
CodeMirror и textarea читают текущее содержимое и выделение после завершения
upload, поэтому параллельные правки сохраняются. Следующий файл можно выбрать
после завершения предыдущего, включая повторный выбор того же файла.

Filesystem GET использует защищённый `LocalObjectStorage`, проверяет SHA-256,
отдаёт MIME, `nosniff` и immutable cache. Namespace проксируют конфигурации
Vite всех трёх приложений,
[`E2E gateway`](../scripts/e2e_gateway.py) и
[`nginx`](../deploy/nginx/vmshpwa.conf.template).
Python/TS разрешают только канонический относительный URL этого namespace
в ссылках; изображения и остальные внешние URL сохраняют прежнюю политику.

Ссылки не создают строки `media_assets`/`news_media`.
[`media inventory`](media-inventory-and-retention.md) не сканирует Markdown/AST:
его `unreferencedKeys` не является основанием удалить файл.

## Проверки

Реализовано локально 2 октября 2026. Проверки и снимки:
[`pwa_tests/reports/rich-file-attachments/README.md`](../../pwa_tests/reports/rich-file-attachments/README.md).

- Backend:
  [`test_rich_files.py`](../../pwa_tests/integration/test_rich_files.py) —
  все 15 форматов, неизменность байтов/MIME/URL, граница 50 МиБ,
  невалидный/пустой файл, multipart, storage errors, права, traversal/symlinks.
- Контракт/transport:
  [`rich-files.test.ts`](../packages/contracts/src/rich-files.test.ts),
  [`rich-media-client.test.ts`](../packages/app-shell/src/rich-media-client.test.ts).
- UI:
  [`staff-file-upload.test.tsx`](../apps/staff/src/staff-file-upload.test.tsx),
  [`rich-markdown-editor.test.tsx`](../apps/staff/src/rich-markdown-editor.test.tsx),
  [`staff-lesson-block-editor.test.tsx`](../apps/staff/src/staff-lesson-block-editor.test.tsx),
  [`stories`](../apps/staff/src/staff-file-upload.stories.tsx) с accessibility gate.
- [`rich-file-attachments.spec.ts`](../e2e/rich-file-attachments.spec.ts) через
  `make pwa-e2e-rich-files`: news, banner, before/after, сохранение и публикация,
  изменение подписи, Student/Family, публичный GET исходных байтов;
  Chromium/WebKit/Firefox без S3/Telegram/Google credentials.

SQLite migrations и новые настройки storage не требуются. Production-выпуск
в этот инкремент не входил; S3 использует уже настроенный публичный bucket/prefix.

## Production — выпуск 2 октября 2026

Владелец разрешил commit/push, VMSH webhook и ручной TLF cutover. Фича
перенесена поверх уже выпущенного progressive task release; незавершённый
локальный fresh-problem-set инкремент исключён из выпуска.

Ручной [deploy_rich_files.sh](../../docs/deploy/tlf-app/deploy_rich_files.sh)
собирает frozen production bundles до остановки writers, делает backups,
проверяет отсутствие migration/dependency изменений, добавляет только
публичный nginx namespace и сохраняет прежние host/TLS/socket/media настройки.
[Read-only checker](../../docs/deploy/tlf-app/rich_files_data_check.py) сравнивает
все product tables, включая support receipts и сырые Zoom events. Backend
health предшествует переключению frontend; rollback сохраняет БД и S3.
Production-результат будет добавлен после cutover и HTTP smoke.
