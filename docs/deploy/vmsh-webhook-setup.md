# GitHub webhook и автоматический deploy ВМШ

Webhook принимает только подписанные GitHub `push` для заранее перечисленных
`repository + ref`. Из запроса нельзя передать shell-команду, путь, пользователя
или revision. CGI работает как `vmsh_webhook`, а `sudoers` разрешает ему только
запуск root-owned deploy-скрипта без аргументов от имени `vmsh_tasks_bot`.

Все изменяемые артефакты находятся под `/web/vmsh_tasks_bot/deploy`. В `/etc`
остаются только systemd symlinks, обязательный файл `sudoers` и одна строка
`include` в уже существующем nginx-конфиге сайта.

## 1. Пакеты и отдельный пользователь

Выполнить от обычного административного пользователя:

```bash
sudo apt install -y fcgiwrap python3-yaml acl

sudo useradd \
  --system \
  --user-group \
  --home-dir /web/vmsh_tasks_bot/deploy \
  --no-create-home \
  --shell /usr/sbin/nologin \
  vmsh_webhook

# /web и /web/vmsh_tasks_bot закрыты для посторонних. Webhook получает только
# право пройти к своему deploy-каталогу, но не group-write ко всему checkout.
sudo setfacl -m u:vmsh_webhook:--x /web
sudo setfacl -m u:vmsh_webhook:--x /web/vmsh_tasks_bot

sudo install -d -o root -g root -m 0755 \
  /web/vmsh_tasks_bot/deploy \
  /web/vmsh_tasks_bot/deploy/bin \
  /web/vmsh_tasks_bot/deploy/systemd
sudo install -d -o root -g vmsh_webhook -m 0750 \
  /web/vmsh_tasks_bot/deploy/config \
  /web/vmsh_tasks_bot/deploy/secrets

sudo install -d -o vmsh_webhook -g vmsh_webhook -m 0750 \
  /web/vmsh_tasks_bot/deploy/logs/webhook
sudo install -d -o vmsh_tasks_bot -g vmsh_tasks_bot -m 0750 \
  /web/vmsh_tasks_bot/deploy/logs/runs \
  /web/vmsh_tasks_bot/deploy/runtime/deploy
sudo install -d -o vmsh_webhook -g nginx -m 0750 \
  /web/vmsh_tasks_bot/deploy/runtime/webhook
```

Если пользователь уже создан, `useradd` завершится сообщением об этом; остальные
команды можно выполнять повторно.

## 2. Установить неизменяемые исполняемые файлы и конфигурацию

```bash
cd /web/vmsh_tasks_bot/vmsh_tasks_bot

sudo install -o root -g root -m 0755 \
  docs/deploy/vmsh-webhook.cgi \
  /web/vmsh_tasks_bot/deploy/bin/vmsh-webhook.cgi

sudo install -o root -g root -m 0755 \
  docs/deploy/deploy-vmsh-tasks-bot.sh \
  /web/vmsh_tasks_bot/deploy/bin/deploy-vmsh-tasks-bot.sh

sudo install -o root -g vmsh_webhook -m 0640 \
  docs/deploy/vmsh-webhook-config.yml \
  /web/vmsh_tasks_bot/deploy/config/webhook.yml

sudo install -o root -g root -m 0644 \
  docs/deploy/vmsh-webhook.service \
  /web/vmsh_tasks_bot/deploy/systemd/vmsh-webhook.service
sudo install -o root -g root -m 0644 \
  docs/deploy/vmsh-webhook.socket \
  /web/vmsh_tasks_bot/deploy/systemd/vmsh-webhook.socket

sudo install -o root -g root -m 0644 \
  docs/deploy/vmsh-webhook-nginx.conf \
  /web/vmsh_tasks_bot/deploy/config/vmsh-webhook-nginx.conf

sudo install -o root -g root -m 0440 \
  docs/deploy/vmsh-webhook-sudoers \
  /etc/sudoers.d/vmsh-webhook
sudo visudo -cf /etc/sudoers.d/vmsh-webhook
```

Root ownership намеренный. Push, изменивший файлы в `docs/deploy`, не может сам
заменить код, разрешённый в `sudoers`, systemd или nginx. После осознанного
изменения этих файлов блок установки выполняется вручную ещё раз.

## 3. Создать GitHub secret

```bash
openssl rand -hex 32 | sudo tee \
  /web/vmsh_tasks_bot/deploy/secrets/github-vmsh-tasks-bot.secret >/dev/null
sudo chown root:vmsh_webhook \
  /web/vmsh_tasks_bot/deploy/secrets/github-vmsh-tasks-bot.secret
sudo chmod 0640 \
  /web/vmsh_tasks_bot/deploy/secrets/github-vmsh-tasks-bot.secret

# Показать один раз и скопировать значение в настройки GitHub webhook.
sudo cat /web/vmsh_tasks_bot/deploy/secrets/github-vmsh-tasks-bot.secret
```

Для каждого будущего repository рекомендуется отдельный secret-файл.

## 4. Инициализировать маркер уже развёрнутой revision

Маркер меняется только после полностью успешного deploy. Поэтому неудачную
сборку можно повторить, даже если deployment checkout уже смотрит на новый SHA.

```bash
sudo su vmsh_tasks_bot -s /usr/bin/bash

set -euo pipefail
cd /web/vmsh_tasks_bot/vmsh_tasks_bot
git fetch origin vmshpwa --prune
git checkout vmshpwa
git pull --ff-only origin vmshpwa
git rev-parse HEAD > \
  /web/vmsh_tasks_bot/deploy/runtime/deploy/vmsh-tasks-bot.revision
chmod 0640 \
  /web/vmsh_tasks_bot/deploy/runtime/deploy/vmsh-tasks-bot.revision
exit
```

## 5. Включить socket-activated fcgiwrap

```bash
sudo ln -sfn \
  /web/vmsh_tasks_bot/deploy/systemd/vmsh-webhook.socket \
  /etc/systemd/system/vmsh-webhook.socket
sudo ln -sfn \
  /web/vmsh_tasks_bot/deploy/systemd/vmsh-webhook.service \
  /etc/systemd/system/vmsh-webhook.service

sudo systemd-analyze verify \
  /web/vmsh_tasks_bot/deploy/systemd/vmsh-webhook.socket \
  /web/vmsh_tasks_bot/deploy/systemd/vmsh-webhook.service
sudo systemctl daemon-reload
sudo systemctl enable --now vmsh-webhook.socket

sudo systemctl status vmsh-webhook.socket --no-pager -l
sudo ss -xl | grep /web/vmsh_tasks_bot/deploy/runtime/webhook/vmsh-webhook.sock
```

Service стартует при первом обращении nginx. После первого запроса проверить:

```bash
sudo systemctl status vmsh-webhook.service --no-pager -l
sudo journalctl -u vmsh-webhook.service -n 100 --no-pager
```

## 6. Подключить location к существующему nginx

Внутрь существующего TLS `server { ... }` для `vmsh.shashkovs.ru` добавить одну
строку. Exact location может находиться рядом с другими API locations:

```nginx
include /web/vmsh_tasks_bot/deploy/config/vmsh-webhook-nginx.conf;
```

Затем:

```bash
sudo nginx -t
sudo systemctl reload nginx

# GET запрещён nginx и не должен запускать CGI.
curl -i https://vmsh.shashkovs.ru/_github/webhook
```

Ожидается `403`. Для неподписанного POST ожидается `403 Invalid webhook
signature`, а не `502`:

```bash
curl -i \
  -X POST \
  -H 'Content-Type: application/json' \
  -H 'X-GitHub-Event: ping' \
  -H 'X-GitHub-Delivery: local-unsigned-check' \
  --data '{"repository":{"full_name":"ShashkovS/vmsh_tasks_bot"}}' \
  https://vmsh.shashkovs.ru/_github/webhook
```

## 7. Настроить webhook в GitHub

Repository → **Settings → Webhooks → Add webhook**:

- Payload URL: `https://vmsh.shashkovs.ru/_github/webhook`;
- Content type: `application/json`;
- Secret: содержимое `github-vmsh-tasks-bot.secret`;
- SSL verification: включена;
- Events: `Just the push event`;
- Active: включён.

После сохранения GitHub отправит `ping`. В Recent Deliveries должен быть ответ
`200 Signed GitHub ping accepted`. Deploy запускает только push в
`refs/heads/vmshpwa`; другие ветки получают `202` и ничего не меняют.

## 8. Проверить права и первый запуск

```bash
sudo -l -U vmsh_webhook
sudo -l -U vmsh_tasks_bot

sudo su vmsh_tasks_bot -s /usr/bin/bash
/web/vmsh_tasks_bot/deploy/bin/deploy-vmsh-tasks-bot.sh
exit
```

Первый ручной запуск после инициализации маркера должен написать `No changes to
deploy`. После тестового push смотреть:

```bash
sudo tail -n 200 \
  /web/vmsh_tasks_bot/deploy/logs/webhook/webhook.log
sudo tail -n 300 \
  /web/vmsh_tasks_bot/deploy/logs/webhook/deploy-launch.log
sudo tail -n 300 \
  /web/vmsh_tasks_bot/deploy/logs/runs/vmsh-tasks-bot.log
```

## Что именно делает deploy

Скрипт берёт неблокирующий `flock`, получает только `origin/vmshpwa`, вычисляет
diff от последней успешно развёрнутой revision и затем:

- обновляет `uv`/`pnpm` dependencies только при изменении lock/manifests;
- при backend-изменениях до остановки production-процессов прогоняет PWA
  Python tests на восьми изолированных workers;
- при frontend-изменениях запускает lint, typecheck, unit tests, production
  build, Brotli, package/verify; release активируется только после backend;
- при изменении schema делает проверенный SQLite backup, останавливает оба
  процесса-писателя и применяет migrations; обычные Python-изменения не
  требуют остановки перед restart;
- после backend-изменений проверяет toolchain, перезапускает legacy и PWA
  services и проверяет runtime endpoints;
- после успеха делает второй SQLite backup и обновляет revision marker;
- при ошибке frontend после переключения возвращает предыдущий static release;
- отправляет результат в `exceptions_channel` существующего production JSON
  через настроенного там Telegram-бота.

Backend-код и schema автоматически назад не откатываются. Если migration
оборвалась, оба процесса остаются остановленными до ручной проверки и
восстановления из созданного backup. Это безопаснее попытки запустить старый
код поверх частично изменённой schema.

Скрипт не вызывает `git clean` и не удаляет untracked-файлы. Если такой файл
реально мешает переключиться на новую revision, обычная защита `git checkout`
остановит deploy. Игнорируемые production credentials не затрагиваются.

## Добавление другого проекта

1. Создать отдельный root-owned deploy script без параметров.
2. Добавить repository, secret и exact ref в `webhook.yml`.
3. Добавить в `/etc/sudoers.d/vmsh-webhook` только exact script и target user.
4. Выполнить `visudo -cf` и добавить webhook с соответствующим secret в GitHub.
   YAML и CGI читаются заново на каждом запросе; restart нужен только после
   изменения systemd unit.

Не добавлять в YAML массив произвольных `post_deploy` shell-команд: это
превращает конфигурационный файл в удалённый shell и усложняет аудит `sudoers`.
