# Production deployment

## Текущая модель

CI-платформа пока не вводится. Production deployment запускается защищённым server-side webhook и всегда разворачивает конкретный commit из основной ветки. Webhook не принимает shell fragments, paths или произвольные revision от публичного request.

Production host: `vmsh.shashkovs.ru`. Желаемый staging host: `devvmsh.shashkovs.ru`. Плановое окно обслуживания с недоступностью сервиса допустимо; blue/green переключение не является требованием первой версии.

## Последовательность

1. Взять deploy lock и проверить подпись/secret webhook.
2. Получить новый commit и вычислить diff от текущей production revision.
3. Запустить backup SQLite до migrations/restart и дождаться его перед изменением backend.
4. Если изменились `pyproject.toml`/`uv.lock`, выполнить frozen production sync в выделенное окружение.
5. Если изменились `vmshpwa/pnpm-lock.yaml`, `pnpm-workspace.yaml` или любой `package.json`, выполнить `pnpm install --frozen-lockfile` под закреплёнными Node 26 и pnpm 11.15.1.
6. Для frontend-изменений выполнить format-check, lint, typecheck, unit/Storybook tests и production build. Не собирать с `VITE_ENABLE_MSW` или `VITE_PROTOTYPE`.
7. Применить yoyo migrations до переключения backend revision. Каждая migration имеет backup/rollback procedure.
8. Атомарно переключить static assets, перезапустить gunicorn и связанные workers только при соответствующих изменениях.
9. Под service profile выполнить toolchain preflight для включённых capabilities: config defaults `pdflatex`, `pdf2svg`, `cwebp`, `magick` должны разрешиться через его `PATH` либо через явный absolute override; сохранить redacted version report.
10. Проверить production `s3_url`, bucket и наличие access/secret key из `creds_prod/vmsh_bot_config_prod.json`, затем выполнить redacted Beget S3 capability probe; значения ключей и signed URLs не печатать.
11. Проверить три audience health/runtime URL, static history fallback, WebSocket upgrade, CSP/security headers и service-worker files.
12. Запустить detached post-deploy backup и отправить оператору итог с revision и статусами.

Yoyo apply выполняется только этим отдельным шагом под deploy lock. Обычный startup/connect не пытается применить migrations из каждого gunicorn/Telegram процесса: он сверяет ожидаемую schema version и останавливается до обслуживания при mismatch.

Toolchain config хранит executable name/path, а не shell command. Локальные Homebrew/user-bin paths не переносятся в production config автоматически. Production unit обязан иметь корректный `PATH` именно у пользователя сервиса; интерактивный login shell владельца не является доказательством. Если capability сознательно отключена значением `None`, соответствующий workflow не включается. Missing/non-executable required tool останавливает deploy/readiness до переключения revision.

S3 secret source выбирается профилем: ручная local/test integration использует test credential file, production — production credential file. Fast unit/agent/E2E не обращаются к внешнему bucket. Loader для PWA извлекает только allowlisted `s3_url`, `s3_bucket_name`, `s3_access_key`, `s3_secret_key` и не должен из-за этого инициализировать Telegram/Google. Любой deploy/health report редактирует access/secret key и полный signed URL.

Не следует применять `git reset --hard` или `git clean` в общей рабочей копии разработчика. Такие команды допустимы только внутри специально созданного deployment checkout, который не содержит пользовательских данных и незакоммиченной работы.

## Change detection

- frontend dependency: `vmshpwa/pnpm-lock.yaml`, `vmshpwa/pnpm-workspace.yaml`, `vmshpwa/package.json`, `vmshpwa/apps/*/package.json`, `vmshpwa/packages/*/package.json`;
- frontend source/config: `vmshpwa/apps`, `vmshpwa/packages`, `vmshpwa/.storybook`, Vite/TypeScript/ESLint/Stylelint/Playwright configs;
- Python dependency: `pyproject.toml`, `uv.lock`;
- backend: `apps`, `models`, `db_methods`, `helpers`, `handlers`, `migrations`, `main.py`;
- documentation-only изменения deployment не перезапускают runtime.

## Checks

Playwright собирает production bundles и проверяет их через `vite preview`; это единый gate для production splitting, manifests, service workers, функциональных сценариев и визуальных snapshots. После deployment отдельно запускается короткий smoke уже разложенных compiled assets. Визуальные snapshots пока воспроизводятся на машине владельца под macOS и не обновляются автоматически на сервере.

## Backup, rollout и инциденты

- SQLite резервируется три раза в день и дополнительно перед deployment. Этого достаточно для первой версии; recovery drill и проверка целостности остаются обязательной эксплуатационной процедурой.
- Для S3 отдельная резервная копия в первой версии не создаётся. Оригиналы ученических изображений после клиентской WebP-конвертации не хранятся, старые версии до проверки не сохраняются. Зафиксированные evidence и отправленные преподавателем артефакты не перезаписываются и сохраняются бессрочно до ручной очистки.
- Серьёзные ошибки deployment, backend, content pipeline, Telegram mirror и object storage отправляются в специальную Telegram-группу операторов.
- Функции PWA включаются сразу для всех групп после успешной приёмки. Постепенный rollout по отдельным учебным группам не нужен.
- Перед рискованной миграцией выполняется rehearsal на копии production SQLite с согласованными файлами DB/WAL/SHM. Эта копия использует отдельный runtime и никогда не подключается к production workers.
