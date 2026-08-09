# Production rollout checklist

Этот чек-лист собирает уже реализованные команды Phase 11 в один порядок
действий. Он не подменяет [`deployment.md`](deployment.md): там описана модель,
здесь оператор фиксирует доказательства одного конкретного выпуска.

Для первого закрытого тестового запуска используется сокращённый
[`план пилотного деплоя`](../dev/development-plan/23-pilot-deployment.md). Этот
документ остаётся полным чек-листом публичного rollout и не требует закрывать
каждый косметический пункт до начала пилота.

Чек-лист заполняется копией вне репозитория. В неё нельзя вставлять cookies,
пароли, Telegram/S3 credentials, полные публичные media URL или персональные
данные. Для каждого выполненного пункта достаточно времени, статуса и пути к
privacy-safe report.

## Идентификация выпуска

- [ ] Записаны точный Git revision, дата, оператор и утверждённый HTTPS FQDN.
- [ ] Записаны текущая и целевая версии схемы SQLite.
- [ ] Указаны предыдущий рабочий release ID и путь rollback.
- [ ] Подтверждено maintenance window; новые PWA workers, legacy Telegram
      writer и jobs не будут писать в SQLite во время migration.
- [ ] Проверено, что runtime DB, media, credentials и release directories не
      находятся внутри очищаемого deployment checkout.

## До остановки writers

- [ ] `make pwa-format pwa-lint pwa-typecheck pwa-test pwa-storybook-test
      pwa-build` завершены успешно на точном revision.
- [ ] `make python-test telegram-history-test` завершены успешно.
- [ ] Production-build Playwright matrix завершена в Chromium, Firefox и
      WebKit; launcher failure не записывается как pass.
- [ ] Изолированная migration rehearsal выполнена командой
      `make pwa-phase11-course-rehearsal`; source `db/vmsh.db` не изменён.
- [ ] Изолированный restore rehearsal выполнен командой
      `make pwa-phase11-restore-rehearsal`; integrity/read-model checks зелёные,
      измеренные RPO/RTO записаны без содержимого данных.
- [ ] Dependency audit просмотрен; известные исключения имеют владельца и
      решение, а не молчаливый skip.
- [ ] Создан согласованный pre-deploy SQLite backup и записан его opaque ID.

## Сборка и статический release

- [ ] Node 26, pnpm 11.15.1, Python 3.14 и frozen lockfiles подтверждены под
      production service user.
- [ ] Frontend собран без prototype/MSW и упакован командой
      `make pwa-phase11-release-package` с точным `PWA_RELEASE_ID`.
- [ ] `make pwa-phase11-release-verify` подтвердил manifest и checksums до
      активации.
- [ ] Redacted toolchain probe подтвердил нужные `pdflatex`, `pdf2svg`, `cwebp`
      и `magick` именно в service profile.
- [ ] Storage config содержит полный Hetzner S3 tuple и не использует test
      bucket/profile. Credential values не попали в вывод.

## Maintenance window

- [ ] Остановлены и завершились все процессы, способные писать в общую SQLite.
- [ ] Exclusive lifecycle lock получен до migration; WAL/SHM не копируются
      отдельно от согласованной backup-операции.
- [ ] Yoyo migrations применены отдельной командой; runtime startup их не
      запускает. Итоговая schema version совпала с release manifest.
- [ ] `make pwa-phase11-release-activate` атомарно переключил проверенный
      frontend release.
- [ ] Rendered systemd unit/environment прошли `make pwa-systemd-check`;
      environment file имеет mode `0600`.
- [ ] Rendered nginx config прошёл `make pwa-nginx-check` до reload.
- [ ] PWA API поднят двумя workers; legacy Telegram adapter поднят отдельно и
      не загружает Google в PWA process.

## После запуска

- [ ] `make pwa-production-http-smoke` прошёл для точного HTTPS origin и
      ожидаемого runtime instance.
- [ ] Проверены authenticated login/session revoke, WebSocket reconnect с
      обязательным refetch, API/SPA routing и nginx login rate limit.
- [ ] Выполнены один безопасный Student read и один admin read без изменения
      production content.
- [ ] На доступном Android проверены install/update/offline shell/push; iPhone
      проверен по возможности. Устройство и browser version записаны.
- [ ] Sentry release/environment/audience видны, synthetic error не содержит
      cookie, token, answer, photo URL или comment.
- [ ] Проверены operator alerts для backend, content, storage и Telegram без
      приватного payload.
- [ ] Запущен post-deploy backup и записан его opaque ID.
- [ ] Владелец подтвердил Student, Family и Staff smoke; Telegram fallback
      остаётся рабочим.

## Немедленный rollback

Rollback запускается, если migration/startup/health не завершены, security
headers ломают приложение, новый release теряет данные/черновики, смешивает
audience или Telegram adapter перестаёт работать.

- [ ] Остановлены новые workers и все writers.
- [ ] Если schema совместима, выполнен `make pwa-phase11-release-rollback` на
      заранее записанный release ID.
- [ ] Если schema несовместима, применена заранее проверенная migration rollback
      либо восстановлен согласованный pre-deploy backup. Это решение нельзя
      принимать после начала deployment без готового rehearsal.
- [ ] Запущены предыдущие backend/Telegram revisions и выполнен короткий public
      HTTP/auth/Telegram smoke.
- [ ] Инцидент, потеря данных и фактические RPO/RTO записаны; повторный rollout
      запрещён до отдельного решения.

## Итоговая папка доказательств

Она должна содержать release/config/schema manifests, redacted toolchain и
storage reports, test summaries, backup/restore evidence, deploy/rollback
result, public smoke, device matrix и owner acceptance. Отсутствующий внешний
gate помечается `NOT RUN` с причиной; его нельзя превращать в `PASS` ссылкой на
локальный unit test.
