# Production deployment

Исполняемый порядок одного выпуска и набор сохраняемых доказательств вынесены
в [`production-rollout-checklist.md`](production-rollout-checklist.md). Чек-лист
не считается заполненным заранее: server, browser/device и owner gates получают
статус только после фактического запуска.

## Текущая модель

CI-платформа пока не вводится. Production deployment запускается защищённым server-side webhook и всегда разворачивает конкретный commit из основной ветки. Webhook не принимает shell fragments, paths или произвольные revision от публичного request.

Hostname нового PWA ещё не принят владельцем и является обязательным
render-time параметром `@@PUBLIC_HOST@@`, а не предположением из существующего
legacy-сайта. Production и optional staging должны получить разные явно
утверждённые FQDN. Плановое окно обслуживания с недоступностью сервиса
допустимо; blue/green переключение не является требованием первой версии.

Все production-артефакты PWA, включая runtime environment, unit source, Unix
socket и media/write каталоги, находятся под `/web/vmsh_tasks_bot/vmshpwa`.
Systemd и nginx получают только symlink в своих стандартных каталогах. `uv`
запускается из shell пользователя приложения: на сервере нужно выполнить
`sudo su vmsh_tasks_bot -s /usr/bin/bash`, затем перейти в
`/web/vmsh_tasks_bot/vmsh_tasks_bot` и только после этого запускать `uv sync`.
Вызов `sudo -H -u vmsh_tasks_bot uv ...` не используется, потому что uv
установлен в пользовательском окружении `vmsh_tasks_bot`.

## Последовательность

1. Взять deploy lock и проверить подпись/secret webhook.
2. Получить новый commit и вычислить diff от текущей production revision.
3. Запустить backup SQLite до migrations/restart и дождаться его перед изменением backend.
4. Если изменились `pyproject.toml`/`uv.lock`, выполнить frozen production sync в выделенное окружение.
5. Если изменились `vmshpwa/pnpm-lock.yaml`, `pnpm-workspace.yaml` или любой `package.json`, выполнить `pnpm install --frozen-lockfile` под закреплёнными Node 26 и pnpm 11.15.1.
6. Для frontend-изменений выполнить format-check, lint, typecheck и
   unit/Storybook tests. Финальные bundles собирать только отдельной командой:

   ```shell
   make pwa-production-build \
     PWA_RELEASE_ID=<lowercase-release-id> \
     VITE_PUBLIC_MEDIA_ORIGIN=https://<public-media-host> \
     VITE_SENTRY_DSN=https://<public-key>@<sentry-ingest-host>/<project-id>
   ```

   Значения `VITE_*` по контракту Vite попадают в клиентский bundle и поэтому
   не должны содержать secrets. Команда принудительно отключает MSW/prototype,
   связывает Sentry release с `PWA_RELEASE_ID` и создаёт в каждом приложении
   `build-provenance.json`. Обычный `make pwa-build` остаётся credential-free
   verification build и намеренно не может быть упакован как production
   release. `make pwa-phase11-release-package` принимает только одинаковый
   production provenance всех трёх приложений с тем же release ID. Команды
   package/verify/activate/rollback требуют явный `PWA_RELEASE_ROOT`; на сервере
   это отдельный каталог статических релизов вне deployment checkout, и тот же
   путь с `/current` передаётся в nginx как `@@STATIC_ROOT@@`.
7. Для schema maintenance остановить и дождаться завершения Gunicorn master/workers, Telegram adapter и всех background jobs, которые могут открыть общую SQLite. Rolling HUP для этого шага запрещён: перекрывающиеся shared locks намеренно не оставляют окна для migration.
8. Получить exclusive database lifecycle lock и применить yoyo migrations до переключения backend revision. Каждая migration имеет backup/rollback procedure; занятый lock прерывает deploy до любого DDL.
9. Атомарно переключить static assets и запустить gunicorn/связанные workers только при соответствующих изменениях.
10. Под service profile выполнить toolchain preflight для включённых capabilities: config defaults `pdflatex`, `pdf2svg`, `cwebp`, `magick` должны разрешиться через его `PATH` либо через явный absolute override; сохранить redacted version report.
11. Проверить production Hetzner `s3_url`, region, bucket и наличие access/secret key из `creds_prod/vmsh_bot_config_prod.json`, затем выполнить redacted S3 capability probe; значения ключей и object URLs не печатать.
12. Установить rendered nginx template/snippet и выполнить проверку ниже;
    отсутствие nginx/config, exact public host или полностью rendered site
    является незакрытым proof, а не skip.

    ```sh
    VMSH_PWA_PUBLIC_HOST=<approved-fqdn> \
      VMSH_PWA_NGINX_CONFIG=/etc/nginx/nginx.conf \
      VMSH_PWA_NGINX_SITE_CONFIG=/web/vmsh_tasks_bot/vmshpwa/runtime/nginx/vmshpwa.conf \
      make pwa-nginx-check
    ```

13. Render отдельного PWA systemd unit и owner-only environment file из
    [`vmshpwa/deploy/systemd`](../deploy/systemd/README.md), затем проверить их
    на production host:

    ```sh
    VMSH_PWA_SYSTEMD_UNIT=/web/vmsh_tasks_bot/vmshpwa/runtime/vmshpwa.service \
      VMSH_PWA_SYSTEMD_ENV=/web/vmsh_tasks_bot/vmshpwa/runtime/vmshpwa.env \
      make pwa-systemd-check
    ```

    Unit фиксирует `pwa-production`, отключённый prototype и два worker.
    Кабинеты остаются на Unix socket, а второй bind `127.0.0.1:8000` обслуживает
    локальный Prometheus scrape; Telegram/Google остаются в отдельном legacy
    service. Environment file имеет exact mode `0600`; unresolved markers и
    adapter/profile overrides блокируют deploy.
14. Проверить три audience health/runtime URL, static history fallback,
    WebSocket upgrade, spoofed forwarding rejection, настоящий login `429` с
    `Retry-After`, CSP/security headers и service-worker files.
15. Запустить detached post-deploy backup и отправить оператору итог с revision и статусами.

Yoyo apply выполняется только этим отдельным шагом под deploy lock. Обычный startup/connect не пытается применить migrations из каждого gunicorn/Telegram процесса: он сверяет ожидаемую schema version и останавливается до обслуживания при mismatch.

Toolchain config хранит executable name/path, а не shell command. Локальные Homebrew/user-bin paths не переносятся в production config автоматически. Production unit обязан иметь корректный `PATH` именно у пользователя сервиса; интерактивный login shell владельца не является доказательством. Если capability сознательно отключена значением `None`, соответствующий workflow не включается. Missing/non-executable required tool останавливает deploy/readiness до переключения revision.

S3 secret source выбирается профилем: ручная local/test integration использует test credential file, production — production credential file. Fast unit/agent/E2E не обращаются к внешнему bucket. Loader для PWA извлекает только allowlisted `s3_url`, `s3_bucket_name`, `s3_access_key`, `s3_secret_key` и не должен из-за этого инициализировать Telegram/Google. Любой deploy/health report редактирует access/secret key и полный signed URL.

## nginx и trusted proxy

Канонические артефакты находятся в
[`vmshpwa/deploy/nginx`](../deploy/nginx/README.md). Один TLS host обслуживает
`/student`, `/family`, `/staff`; API и WebSocket locations расположены перед SPA
fallback. Login ограничен отдельной per-IP zone `6r/m`, burst `4`, rejected
status `429` и `Retry-After: 60`; общий backend throttle по login/account остаётся
вторым независимым уровнем. Общий API body ceiling — `64m`, WebSocket handshake
— `64k`, endpoint-specific aiohttp limits всё равно строже. HTTP upstream
timeouts — `5s/120s/120s`, WebSocket read/send — `75s` при heartbeat `25s`.

Рекомендуемый production upstream — Unix socket. Его rendered path должен
точно совпасть с `VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON`; directory/socket
имеют `0750`/`0660` и отдельную service group. Loopback TCP поддерживается
explicit `127.0.0.1/32,::1/128`, но backend не слушает public interface, и этот
вариант считается доверием к контролируемому host, а не identity конкретного
local process. Клиентский `Forwarded` и весь `X-Forwarded-*` nginx заменяет/
подавляет; приложение не использует aiohttp `request.remote` как готовую
proxy-truth.

Публичный exact location `/metrics` всегда возвращает `404` и не проксируется.
Prometheus обращается напрямую к `http://127.0.0.1:8000/metrics`; этот listener
не заменяет Unix upstream и никогда не публикуется на внешнем интерфейсе.

Структурные тесты гарантируют namespaces, header replacement, WebSocket
upgrade, rate-limit и fail-closed CSP markers. Настоящий syntax proof создаёт
только [`nginx_config_check.py`](../scripts/nginx_config_check.py) над
установленным config: helper возвращает non-zero при отсутствии binary/config,
unresolved markers, timeout или ошибке `nginx -t`.

## systemd profile

PWA API запускается отдельным unit из
[`vmshpwa/deploy/systemd`](../deploy/systemd/README.md). Он не стартует polling,
не импортирует Google и не заменяет legacy Telegram service. Командная строка
фиксирует `VMSH_RUNTIME_PROFILE=pwa-production` и
`VMSH_PWA_PROTOTYPE=false`, потому что systemd `EnvironmentFile=` имеет более
высокий приоритет, чем `Environment=`. Rolling `ExecReload` не задаётся:
migrations выполняются только в maintenance window после остановки всех writers.

Локальный checker проверяет структуру и секрет-free configuration report. На
Linux production host он дополнительно требует успешный `systemd-analyze
verify`; реальный `systemctl restart`, socket ownership и health через nginx
остаются отдельным rollout proof.

Unit создаёт `/run/vmsh-prometheus`, очищает stale multiprocess-файлы до старта
Gunicorn и задаёт `PROMETHEUS_MULTIPROC_DIR` до импорта приложения. Hook
[`gunicorn.conf.py`](../../gunicorn.conf.py) вызывает
`multiprocess.mark_process_dead` после выхода worker. После успешного старта
deploy создаёт exact file-discovery target `/etc/prometheus/targets/aiohttp.json`.

Не следует применять `git reset --hard` или `git clean` в общей рабочей копии разработчика. Такие команды допустимы только внутри специально созданного deployment checkout, который не содержит пользовательских данных и незакоммиченной работы.

## Change detection

- frontend dependency: `vmshpwa/pnpm-lock.yaml`, `vmshpwa/pnpm-workspace.yaml`, `vmshpwa/package.json`, `vmshpwa/apps/*/package.json`, `vmshpwa/packages/*/package.json`;
- frontend source/config: `vmshpwa/apps`, `vmshpwa/packages`, `vmshpwa/.storybook`, Vite/TypeScript/ESLint/Stylelint/Playwright configs;
- Python dependency: `pyproject.toml`, `uv.lock`;
- backend: `apps`, `models`, `db_methods`, `helpers`, `handlers`, `migrations`,
  `main.py`, `gunicorn.conf.py`;
- documentation-only изменения deployment не перезапускают runtime.

## Checks

Playwright собирает production bundles и проверяет их вместе с настоящим
aiohttp через lock-aware test-only one-origin gateway; это единый gate для
production splitting, manifests, service workers, функциональных сценариев и
визуальных snapshots. До auth/CSRF gate он не заменяет trusted-proxy/public-origin
модель production nginx. После deployment отдельно запускается короткий smoke
уже разложенных compiled assets. Визуальные snapshots пока воспроизводятся на
машине владельца под macOS и не обновляются автоматически на сервере.

## Backup, rollout и инциденты

- SQLite резервируется три раза в день и дополнительно перед deployment. Этого достаточно для первой версии; recovery drill и проверка целостности остаются обязательной эксплуатационной процедурой.
- Для S3 отдельная резервная копия в первой версии не создаётся. Оригиналы ученических изображений после клиентской WebP-конвертации не хранятся, старые версии до проверки не сохраняются. Зафиксированные evidence и отправленные преподавателем артефакты не перезаписываются и сохраняются бессрочно до ручной очистки.
- Серьёзные ошибки deployment, backend, content pipeline, Telegram mirror и object storage отправляются в специальную Telegram-группу операторов.
- Функции PWA включаются сразу для всех групп после успешной приёмки. Постепенный rollout по отдельным учебным группам не нужен.
- Перед рискованной миграцией выполняется rehearsal на копии production SQLite с согласованными файлами DB/WAL/SHM. Эта копия использует отдельный runtime и никогда не подключается к production workers.
