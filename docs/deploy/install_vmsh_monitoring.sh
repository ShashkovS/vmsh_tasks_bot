#!/usr/bin/env bash

set -Eeuo pipefail
umask 027

if [[ ${EUID} -ne 0 ]]; then
    exec sudo bash "$0" "$@"
fi

on_error() {
    local exit_code=$?
    echo >&2
    echo "ОШИБКА: установка прервана в строке ${BASH_LINENO[0]} (код ${exit_code})." >&2
    echo "Проверьте сообщения непосредственно выше этой строки." >&2
    exit "${exit_code}"
}
trap on_error ERR

WORKDIR="$(mktemp -d /tmp/vmsh-monitoring.XXXXXX)"
cleanup() {
    rm -rf "${WORKDIR}"
}
trap cleanup EXIT

log() {
    printf '\n\033[1;34m==> %s\033[0m\n' "$*"
}

warn() {
    printf '\n\033[1;33mПРЕДУПРЕЖДЕНИЕ: %s\033[0m\n' "$*" >&2
}

die() {
    printf '\n\033[1;31mОШИБКА: %s\033[0m\n' "$*" >&2
    exit 1
}

wait_for_url() {
    local url="$1"
    local seconds="$2"
    local i

    for ((i = 1; i <= seconds; i++)); do
        if curl -fsS --max-time 2 "${url}" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done

    return 1
}

wait_for_grafana() {
    local i

    for ((i = 1; i <= 45; i++)); do
        if curl -fsS \
            --max-time 2 \
            -H 'Host: grafvmsh.shashkovs.ru' \
            http://127.0.0.1:3001/api/health \
            >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done

    return 1
}

nats_monitor_healthy() {
    curl -fsS --max-time 2 http://127.0.0.1:8222/varz 2>/dev/null \
        | python3 -c '
import json
import sys

data = json.load(sys.stdin)
if not isinstance(data, dict) or "server_id" not in data:
    raise SystemExit(1)
' >/dev/null 2>&1
}

nats_monitor_is_local_only() {
    local listener_address
    local listener_found=0

    while IFS= read -r listener_address; do
        [[ -z "${listener_address}" ]] && continue
        listener_found=1

        case "${listener_address}" in
            127.0.0.1:8222|\[::1\]:8222)
                ;;
            *)
                return 1
                ;;
        esac
    done < <(ss -H -ltn 2>/dev/null | awk '$4 ~ /:8222$/ {print $4}')

    ((listener_found == 1))
}

wait_for_nats_monitor() {
    local i

    for ((i = 1; i <= 30; i++)); do
        if nats_monitor_healthy && nats_monitor_is_local_only; then
            return 0
        fi
        sleep 1
    done

    return 1
}

download_and_verify() {
    local url="$1"
    local output="$2"
    local sha256="$3"

    curl \
        --proto '=https' \
        --tlsv1.2 \
        --fail \
        --location \
        --retry 3 \
        --retry-delay 2 \
        --output "${output}" \
        "${url}"

    printf '%s  %s\n' "${sha256}" "${output}" | sha256sum --check --status
}

backup_once() {
    local path="$1"
    local backup="${path}.before-vmsh-monitoring"

    if [[ -e "${path}" && ! -e "${backup}" ]]; then
        cp -a "${path}" "${backup}"
    fi
}

ensure_system_user() {
    local user="$1"

    if ! getent group "${user}" >/dev/null 2>&1; then
        groupadd --system "${user}"
    fi

    if ! id -u "${user}" >/dev/null 2>&1; then
        useradd \
            --system \
            --gid "${user}" \
            --no-create-home \
            --shell /usr/sbin/nologin \
            "${user}"
    fi
}

log "Проверка операционной системы"

[[ -r /etc/os-release ]] || die "Не найден /etc/os-release."
# shellcheck disable=SC1091
source /etc/os-release

[[ "${ID:-}" == "ubuntu" ]] || die "Скрипт рассчитан на Ubuntu, обнаружено: ${ID:-unknown}."
[[ "$(dpkg --print-architecture)" == "amd64" ]] || die "Скрипт рассчитан на amd64."

if [[ "${VERSION_ID:-}" != "26.04" ]]; then
    warn "Скрипт подготовлен для Ubuntu 26.04 amd64; обнаружена версия ${VERSION_ID:-unknown}. Продолжаю, так как используемые пакеты и systemd-unit стандартны."
fi

export DEBIAN_FRONTEND=noninteractive

log "Установка базовых пакетов"

apt-get update
apt-get install -y \
    ca-certificates \
    certbot \
    curl \
    gnupg \
    iproute2 \
    logrotate \
    nginx \
    openssl \
    procps \
    python3 \
    python3-certbot-nginx \
    tar \
    util-linux

log "Создание системных пользователей и каталогов"

ensure_system_user prometheus
ensure_system_user node_exporter
ensure_system_user nginx_exporter
ensure_system_user nats_exporter

install -d -o root       -g prometheus -m 0750 /etc/prometheus
install -d -o root       -g prometheus -m 0750 /etc/prometheus/targets
install -d -o prometheus -g prometheus -m 0750 /var/lib/prometheus

log "Установка Prometheus 3.13.2"

download_and_verify \
    'https://github.com/prometheus/prometheus/releases/download/v3.13.2/prometheus-3.13.2.linux-amd64.tar.gz' \
    "${WORKDIR}/prometheus.tar.gz" \
    '0e8c4d46101bd025ea8265e377d2caabc57f488fc1be1c367f37db69ea41be6f'

mkdir "${WORKDIR}/prometheus"
tar -xzf "${WORKDIR}/prometheus.tar.gz" \
    -C "${WORKDIR}/prometheus" \
    --strip-components=1

install -o root -g root -m 0755 \
    "${WORKDIR}/prometheus/prometheus" \
    /usr/local/bin/prometheus

install -o root -g root -m 0755 \
    "${WORKDIR}/prometheus/promtool" \
    /usr/local/bin/promtool

log "Установка Node Exporter 1.12.1"

download_and_verify \
    'https://github.com/prometheus/node_exporter/releases/download/v1.12.1/node_exporter-1.12.1.linux-amd64.tar.gz' \
    "${WORKDIR}/node_exporter.tar.gz" \
    'b51d8a76aa2a9156a55d501aca6276fae09e262259a5e4e831d2c2222f084e63'

mkdir "${WORKDIR}/node_exporter"
tar -xzf "${WORKDIR}/node_exporter.tar.gz" \
    -C "${WORKDIR}/node_exporter" \
    --strip-components=1

install -o root -g root -m 0755 \
    "${WORKDIR}/node_exporter/node_exporter" \
    /usr/local/bin/node_exporter

log "Установка NGINX Prometheus Exporter 1.5.1"

download_and_verify \
    'https://github.com/nginx/nginx-prometheus-exporter/releases/download/v1.5.1/nginx-prometheus-exporter_1.5.1_linux_amd64.tar.gz' \
    "${WORKDIR}/nginx_exporter.tar.gz" \
    '42ddc7ac31c70021d2a5c10414d473526490769632c1ef430b95d76dd1e3c187'

mkdir "${WORKDIR}/nginx_exporter"
tar -xzf "${WORKDIR}/nginx_exporter.tar.gz" \
    -C "${WORKDIR}/nginx_exporter"

NGINX_EXPORTER_BINARY="$(find "${WORKDIR}/nginx_exporter" -type f -name nginx-prometheus-exporter -print -quit)"
[[ -n "${NGINX_EXPORTER_BINARY}" ]] || die "В архиве не найден nginx-prometheus-exporter."

install -o root -g root -m 0755 \
    "${NGINX_EXPORTER_BINARY}" \
    /usr/local/bin/nginx-prometheus-exporter

log "Установка Prometheus NATS Exporter 0.20.1"

download_and_verify \
    'https://github.com/nats-io/prometheus-nats-exporter/releases/download/v0.20.1/prometheus-nats-exporter-v0.20.1-linux-x86_64.tar.gz' \
    "${WORKDIR}/nats_exporter.tar.gz" \
    'a8798bee71effc2473e48f6b166e63e207a7bb7a7e93ffbb643a1d840607b8ae'

mkdir "${WORKDIR}/nats_exporter"
tar -xzf "${WORKDIR}/nats_exporter.tar.gz" \
    -C "${WORKDIR}/nats_exporter"

NATS_EXPORTER_BINARY="$(find "${WORKDIR}/nats_exporter" -type f -name prometheus-nats-exporter -print -quit)"
[[ -n "${NATS_EXPORTER_BINARY}" ]] || die "В архиве не найден prometheus-nats-exporter."

install -o root -g root -m 0755 \
    "${NATS_EXPORTER_BINARY}" \
    /usr/local/bin/prometheus-nats-exporter

log "Настройка локального monitoring endpoint NATS"

configure_nats_monitoring() {
    local nats_pid=""
    local nats_config=""
    local nats_binary=""
    local nats_unit=""
    local nats_backup=""
    local -a nats_args=()
    local -a nats_pids=()
    local i

    if nats_monitor_healthy && nats_monitor_is_local_only; then
        log "NATS monitoring уже доступен только локально на 127.0.0.1:8222"
        return 0
    fi

    mapfile -t nats_pids < <(pgrep -x nats-server || true)

    if ((${#nats_pids[@]} == 0)); then
        die "Процесс nats-server не найден, хотя ожидалось, что NATS уже запущен."
    fi

    if ((${#nats_pids[@]} > 1)); then
        die "Обнаружено несколько процессов nats-server. Скрипт не будет угадывать, конфигурацию какого экземпляра менять."
    fi

    nats_pid="${nats_pids[0]}"
    nats_binary="$(readlink -f "/proc/${nats_pid}/exe")"
    [[ -x "${nats_binary}" ]] || die "Не удалось определить исполняемый файл nats-server."

    mapfile -d '' -t nats_args < "/proc/${nats_pid}/cmdline"

    for ((i = 0; i < ${#nats_args[@]}; i++)); do
        case "${nats_args[$i]}" in
            -c|--config)
                if ((i + 1 < ${#nats_args[@]})); then
                    nats_config="${nats_args[$((i + 1))]}"
                fi
                ;;
            --config=*)
                nats_config="${nats_args[$i]#--config=}"
                ;;
            -c=*)
                nats_config="${nats_args[$i]#-c=}"
                ;;
        esac
    done

    if [[ -n "${nats_config}" && "${nats_config}" != /* ]]; then
        nats_config="$(readlink -f "/proc/${nats_pid}/cwd")/${nats_config}"
    fi

    if [[ -n "${nats_config}" && -e "${nats_config}" ]]; then
        nats_config="$(readlink -f "${nats_config}")"
    else
        nats_config=""
    fi

    if [[ -z "${nats_config}" ]]; then
        for candidate in \
            /etc/nats/nats-server.conf \
            /etc/nats/nats.conf \
            /etc/nats-server.conf \
            /etc/nats.conf; do
            if [[ -f "${candidate}" ]]; then
                nats_config="${candidate}"
                break
            fi
        done
    fi

    if [[ -z "${nats_config}" ]]; then
        if nats_monitor_healthy && nats_monitor_is_local_only; then
            return 0
        fi
        die "Не удалось найти активный конфигурационный файл NATS. Ожидался аргумент -c/--config или один из стандартных путей /etc/nats/*.conf."
    fi

    nats_unit="$(awk -F/ '{for (i = NF; i >= 1; i--) if ($i ~ /\.service$/) {print $i; exit}}' "/proc/${nats_pid}/cgroup" || true)"

    if [[ -z "${nats_unit}" ]] || ! systemctl status "${nats_unit}" >/dev/null 2>&1; then
        die "NATS запущен не из определяемого systemd-unit. Не меняю ${nats_config}, потому что не смогу безопасно перезапустить и откатить NATS."
    fi

    nats_backup="${nats_config}.backup-vmsh-monitoring-$(date +%Y%m%d-%H%M%S)"
    cp -a "${nats_config}" "${nats_backup}"

    if ! python3 - "${nats_config}" <<'PYTHON'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)

http_re = re.compile(r"^[ \t]*(http|http_port|monitor_port)[ \t]*[:=]", re.IGNORECASE)
https_re = re.compile(r"^[ \t]*(https|https_port)[ \t]*[:=]", re.IGNORECASE)

for line in lines:
    stripped = line.lstrip()
    if stripped.startswith("#") or stripped.startswith("//"):
        continue
    if https_re.match(line):
        print(
            "В конфигурации уже включён HTTPS monitoring endpoint NATS; "
            "автоматически заменять его небезопасно.",
            file=sys.stderr,
        )
        raise SystemExit(2)

result: list[str] = []
inserted = False

for line in lines:
    stripped = line.lstrip()
    commented = stripped.startswith("#") or stripped.startswith("//")

    if not commented and http_re.match(line):
        if not inserted:
            ending = "\r\n" if line.endswith("\r\n") else "\n"
            result.append(f'http: "127.0.0.1:8222"{ending}')
            inserted = True
        continue

    result.append(line)

if not inserted:
    if result and not result[-1].endswith(("\n", "\r\n")):
        result[-1] += "\n"
    if result and result[-1].strip():
        result.append("\n")
    result.append('http: "127.0.0.1:8222"\n')

path.write_text("".join(result), encoding="utf-8")
PYTHON
    then
        cp -a "${nats_backup}" "${nats_config}"
        die "Не удалось безопасно изменить конфигурацию NATS; исходный файл восстановлен."
    fi

    if ! "${nats_binary}" -t -c "${nats_config}"; then
        cp -a "${nats_backup}" "${nats_config}"
        die "Проверка конфигурации NATS не прошла; исходный файл восстановлен."
    fi

    if ! systemctl restart "${nats_unit}"; then
        cp -a "${nats_backup}" "${nats_config}"
        systemctl restart "${nats_unit}" || true
        die "NATS не перезапустился с новой конфигурацией; исходный файл восстановлен."
    fi

    if ! wait_for_nats_monitor; then
        cp -a "${nats_backup}" "${nats_config}"
        systemctl restart "${nats_unit}" || true
        die "NATS monitoring endpoint не появился на 127.0.0.1:8222; исходный файл восстановлен."
    fi

    log "NATS monitoring включён на 127.0.0.1:8222; резервная копия: ${nats_backup}"
}

configure_nats_monitoring

log "Настройка локального NGINX stub_status"

backup_once /etc/nginx/conf.d/vmsh-prometheus-stub-status.conf

cat > /etc/nginx/conf.d/vmsh-prometheus-stub-status.conf <<'NGINX'
server {
    listen 127.0.0.1:18080;
    server_name localhost;

    access_log off;

    location = /stub_status {
        stub_status;
    }

    location / {
        return 404;
    }
}
NGINX

nginx -t
systemctl enable --now nginx
systemctl reload nginx

wait_for_url http://127.0.0.1:18080/stub_status 15 \
    || die "NGINX stub_status не отвечает на 127.0.0.1:18080."

log "Создание systemd-unit для exporter'ов"

backup_once /etc/systemd/system/node_exporter.service
backup_once /etc/systemd/system/nginx-prometheus-exporter.service
backup_once /etc/systemd/system/nats-prometheus-exporter.service

cat > /etc/systemd/system/node_exporter.service <<'UNIT'
[Unit]
Description=Prometheus Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=node_exporter
Group=node_exporter
ExecStart=/usr/local/bin/node_exporter --web.listen-address=127.0.0.1:9100
Restart=on-failure
RestartSec=5s
UMask=0027
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectHostname=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectKernelLogs=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictNamespaces=true
RestrictRealtime=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LockPersonality=true
SystemCallArchitectures=native
CapabilityBoundingSet=

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/nginx-prometheus-exporter.service <<'UNIT'
[Unit]
Description=NGINX Prometheus Exporter
Wants=network-online.target
After=network-online.target nginx.service

[Service]
Type=simple
User=nginx_exporter
Group=nginx_exporter
ExecStart=/usr/local/bin/nginx-prometheus-exporter --web.listen-address=127.0.0.1:9113 --nginx.scrape-uri=http://127.0.0.1:18080/stub_status
Restart=on-failure
RestartSec=5s
UMask=0027
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectHostname=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectKernelLogs=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictNamespaces=true
RestrictRealtime=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LockPersonality=true
SystemCallArchitectures=native
CapabilityBoundingSet=

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/nats-prometheus-exporter.service <<'UNIT'
[Unit]
Description=NATS Prometheus Exporter
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=nats_exporter
Group=nats_exporter
ExecStart=/usr/local/bin/prometheus-nats-exporter -addr 127.0.0.1 -port 7777 -varz -healthz http://127.0.0.1:8222
Restart=on-failure
RestartSec=5s
UMask=0027
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectHostname=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectKernelLogs=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictNamespaces=true
RestrictRealtime=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LockPersonality=true
SystemCallArchitectures=native
CapabilityBoundingSet=

[Install]
WantedBy=multi-user.target
UNIT

if systemctl cat nginx-exporter.service >/dev/null 2>&1; then
    systemctl disable --now nginx-exporter.service || true
fi

if systemctl cat nats-exporter.service >/dev/null 2>&1; then
    systemctl disable --now nats-exporter.service || true
fi

systemctl daemon-reload
systemctl enable \
    node_exporter.service \
    nginx-prometheus-exporter.service \
    nats-prometheus-exporter.service
systemctl restart \
    node_exporter.service \
    nginx-prometheus-exporter.service \
    nats-prometheus-exporter.service

wait_for_url http://127.0.0.1:9100/metrics 20 \
    || die "Node Exporter не отвечает на 127.0.0.1:9100."

wait_for_url http://127.0.0.1:9113/metrics 20 \
    || die "NGINX Exporter не отвечает на 127.0.0.1:9113."

wait_for_url http://127.0.0.1:7777/metrics 20 \
    || die "NATS Exporter не отвечает на 127.0.0.1:7777."

log "Настройка Prometheus"

backup_once /etc/prometheus/prometheus.yml

cat > /etc/prometheus/prometheus.yml <<'YAML'
global:
  scrape_interval: 30s
  scrape_timeout: 10s
  evaluation_interval: 30s

storage:
  tsdb:
    retention:
      time: 60d
      size: 2500MB

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets:
          - "127.0.0.1:9090"
        labels:
          instance: "vmsh.shashkovs.ru"

  - job_name: node
    static_configs:
      - targets:
          - "127.0.0.1:9100"
        labels:
          instance: "vmsh.shashkovs.ru"

  - job_name: nginx
    scrape_interval: 15s
    static_configs:
      - targets:
          - "127.0.0.1:9113"
        labels:
          instance: "vmsh.shashkovs.ru"

  - job_name: nats
    scrape_interval: 15s
    static_configs:
      - targets:
          - "127.0.0.1:7777"
        labels:
          instance: "vmsh.shashkovs.ru"

  # Пока веб-приложение не задеплоено, файл содержит пустой список.
  # После деплоя достаточно добавить 127.0.0.1:8000 в aiohttp.json:
  # Prometheus подхватит цель автоматически, без перезапуска.
  - job_name: aiohttp
    scrape_interval: 15s
    file_sd_configs:
      - files:
          - /etc/prometheus/targets/aiohttp.json
        refresh_interval: 30s

  # Аналогично подготовлена отдельная цель для Telegram-бота,
  # если у него позднее появится собственный /metrics endpoint.
  - job_name: telegram_bot
    scrape_interval: 15s
    file_sd_configs:
      - files:
          - /etc/prometheus/targets/telegram-bot.json
        refresh_interval: 30s
YAML

if [[ ! -e /etc/prometheus/targets/aiohttp.json ]]; then
    cat > /etc/prometheus/targets/aiohttp.json <<'JSON'
[]
JSON
fi

if [[ ! -e /etc/prometheus/targets/telegram-bot.json ]]; then
    cat > /etc/prometheus/targets/telegram-bot.json <<'JSON'
[]
JSON
fi

chown root:prometheus \
    /etc/prometheus/prometheus.yml \
    /etc/prometheus/targets/aiohttp.json \
    /etc/prometheus/targets/telegram-bot.json

chmod 0640 \
    /etc/prometheus/prometheus.yml \
    /etc/prometheus/targets/aiohttp.json \
    /etc/prometheus/targets/telegram-bot.json

backup_once /etc/systemd/system/prometheus.service

cat > /etc/systemd/system/prometheus.service <<'UNIT'
[Unit]
Description=Prometheus Monitoring System
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=prometheus
Group=prometheus
ExecStart=/usr/local/bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/var/lib/prometheus \
  --web.listen-address=127.0.0.1:9090 \
  --query.max-concurrency=4 \
  --query.timeout=1m
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5s
TimeoutStopSec=30s
LimitNOFILE=65536
UMask=0027
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectHostname=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectKernelLogs=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictNamespaces=true
RestrictRealtime=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LockPersonality=true
SystemCallArchitectures=native
CapabilityBoundingSet=
ReadWritePaths=/var/lib/prometheus

[Install]
WantedBy=multi-user.target
UNIT

runuser -u prometheus -- /usr/local/bin/promtool check config /etc/prometheus/prometheus.yml

systemctl daemon-reload
systemctl enable prometheus.service
systemctl restart prometheus.service

wait_for_url http://127.0.0.1:9090/-/ready 30 \
    || die "Prometheus не перешёл в состояние ready."

log "Подключение официального stable-репозитория Grafana и установка Grafana OSS"

install -d -o root -g root -m 0755 /etc/apt/keyrings

curl \
    --proto '=https' \
    --tlsv1.2 \
    --fail \
    --location \
    --output /etc/apt/keyrings/grafana.asc \
    https://apt.grafana.com/gpg-full.key

chmod 0644 /etc/apt/keyrings/grafana.asc

cat > /etc/apt/sources.list.d/grafana.list <<'APT'
deb [signed-by=/etc/apt/keyrings/grafana.asc] https://apt.grafana.com stable main
APT
chmod 0644 /etc/apt/sources.list.d/grafana.list

apt-get update
apt-get install -y grafana
systemctl stop grafana-server.service >/dev/null 2>&1 || true

backup_once /etc/grafana/grafana.ini

if [[ ! -s /etc/grafana/secret_key ]]; then
    openssl rand -hex 32 > /etc/grafana/secret_key
fi

chown root:grafana /etc/grafana/secret_key
chmod 0640 /etc/grafana/secret_key

cat > /etc/grafana/grafana.ini <<'INI'
[server]
protocol = http
http_addr = 127.0.0.1
http_port = 3001
domain = grafvmsh.shashkovs.ru
enforce_domain = true
root_url = https://grafvmsh.shashkovs.ru/
router_logging = false

[security]
admin_user = admin
secret_key = $__file{/etc/grafana/secret_key}
cookie_secure = true
cookie_samesite = strict
disable_gravatar = true

[users]
allow_sign_up = false
allow_org_create = false
viewers_can_edit = false

[auth.basic]
enabled = true

[auth.anonymous]
enabled = false

[analytics]
enabled = false
reporting_enabled = false
check_for_updates = false
check_for_plugin_updates = false

[plugins]
preinstall_disabled = true

[snapshots]
external_enabled = false

[dashboards]
min_refresh_interval = 15s
versions_to_keep = 10
default_home_dashboard_path = /var/lib/grafana/dashboards/vmsh-overview.json

[log]
mode = console
level = info

[live]
max_connections = 20
INI

chown root:grafana /etc/grafana/grafana.ini
chmod 0640 /etc/grafana/grafana.ini

install -d -o root    -g grafana -m 0750 /etc/grafana/provisioning/datasources
install -d -o root    -g grafana -m 0750 /etc/grafana/provisioning/dashboards
install -d -o grafana -g grafana -m 0750 /var/lib/grafana/dashboards

backup_once /etc/grafana/provisioning/datasources/prometheus.yaml
backup_once /etc/grafana/provisioning/dashboards/vmsh.yaml
backup_once /var/lib/grafana/dashboards/vmsh-overview.json

cat > /etc/grafana/provisioning/datasources/prometheus.yaml <<'YAML'
apiVersion: 1

prune: true

datasources:
  - name: Prometheus
    uid: prometheus
    type: prometheus
    access: proxy
    url: http://127.0.0.1:9090
    isDefault: true
    editable: false
    jsonData:
      httpMethod: POST
      timeInterval: 15s
      prometheusType: Prometheus
      prometheusVersion: 3.13.2
YAML

cat > /etc/grafana/provisioning/dashboards/vmsh.yaml <<'YAML'
apiVersion: 1

providers:
  - name: VMsh
    orgId: 1
    folder: VMsh
    type: file
    disableDeletion: true
    allowUiUpdates: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
YAML

cat > /var/lib/grafana/dashboards/vmsh-overview.json <<'JSON'
{
  "annotations": {
    "list": [
      {
        "builtIn": 1,
        "datasource": {
          "type": "grafana",
          "uid": "-- Grafana --"
        },
        "enable": true,
        "hide": true,
        "iconColor": "rgba(0, 211, 255, 1)",
        "name": "Annotations & Alerts",
        "type": "dashboard"
      }
    ]
  },
  "editable": false,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 1,
  "id": null,
  "links": [],
  "panels": [
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "decimals": 1,
          "max": 100,
          "min": 0,
          "unit": "percent"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 5,
        "w": 6,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto",
        "wideLayout": true
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "100 * (1 - avg(rate(node_cpu_seconds_total{job=\"node\", mode=\"idle\"}[$__rate_interval])))",
          "legendFormat": "CPU",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "CPU usage",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "decimals": 1,
          "max": 100,
          "min": 0,
          "unit": "percent"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 5,
        "w": 6,
        "x": 6,
        "y": 0
      },
      "id": 2,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto",
        "wideLayout": true
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "100 * (1 - node_memory_MemAvailable_bytes{job=\"node\"} / node_memory_MemTotal_bytes{job=\"node\"})",
          "legendFormat": "RAM",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "RAM usage",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "decimals": 1,
          "max": 100,
          "min": 0,
          "unit": "percent"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 5,
        "w": 6,
        "x": 12,
        "y": 0
      },
      "id": 3,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto",
        "wideLayout": true
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "100 * (1 - node_filesystem_avail_bytes{job=\"node\", mountpoint=\"/\", fstype!~\"tmpfs|overlay|squashfs\"} / node_filesystem_size_bytes{job=\"node\", mountpoint=\"/\", fstype!~\"tmpfs|overlay|squashfs\"})",
          "legendFormat": "root",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Root filesystem usage",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "decimals": 0,
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 5,
        "w": 6,
        "x": 18,
        "y": 0
      },
      "id": 4,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto",
        "wideLayout": true
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "gnatsd_varz_connections{job=\"nats\"}",
          "legendFormat": "connections",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "NATS connections",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "unit": "Bps"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 5
      },
      "id": 5,
      "options": {
        "legend": {
          "calcs": [
            "lastNotNull"
          ],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "sum(rate(node_network_receive_bytes_total{job=\"node\", device!=\"lo\"}[$__rate_interval]))",
          "legendFormat": "received",
          "range": true,
          "refId": "A"
        },
        {
          "editorMode": "code",
          "expr": "sum(rate(node_network_transmit_bytes_total{job=\"node\", device!=\"lo\"}[$__rate_interval]))",
          "legendFormat": "transmitted",
          "range": true,
          "refId": "B"
        }
      ],
      "title": "Network throughput",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "unit": "Bps"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 5
      },
      "id": 6,
      "options": {
        "legend": {
          "calcs": [
            "lastNotNull"
          ],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "sum(rate(node_disk_read_bytes_total{job=\"node\"}[$__rate_interval]))",
          "legendFormat": "read",
          "range": true,
          "refId": "A"
        },
        {
          "editorMode": "code",
          "expr": "sum(rate(node_disk_written_bytes_total{job=\"node\"}[$__rate_interval]))",
          "legendFormat": "written",
          "range": true,
          "refId": "B"
        }
      ],
      "title": "Disk throughput",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "unit": "reqps"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 0,
        "y": 13
      },
      "id": 7,
      "options": {
        "legend": {
          "calcs": [
            "lastNotNull"
          ],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "rate(nginx_http_requests_total{job=\"nginx\"}[$__rate_interval])",
          "legendFormat": "requests/s",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "NGINX requests",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 8,
        "y": 13
      },
      "id": 8,
      "options": {
        "legend": {
          "calcs": [
            "lastNotNull"
          ],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "nginx_connections_active{job=\"nginx\"}",
          "legendFormat": "active",
          "range": true,
          "refId": "A"
        },
        {
          "editorMode": "code",
          "expr": "nginx_connections_reading{job=\"nginx\"}",
          "legendFormat": "reading",
          "range": true,
          "refId": "B"
        },
        {
          "editorMode": "code",
          "expr": "nginx_connections_writing{job=\"nginx\"}",
          "legendFormat": "writing",
          "range": true,
          "refId": "C"
        },
        {
          "editorMode": "code",
          "expr": "nginx_connections_waiting{job=\"nginx\"}",
          "legendFormat": "waiting",
          "range": true,
          "refId": "D"
        }
      ],
      "title": "NGINX connections",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "unit": "ops"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 16,
        "y": 13
      },
      "id": 9,
      "options": {
        "legend": {
          "calcs": [
            "lastNotNull"
          ],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "rate(gnatsd_varz_in_msgs{job=\"nats\"}[$__rate_interval])",
          "legendFormat": "in",
          "range": true,
          "refId": "A"
        },
        {
          "editorMode": "code",
          "expr": "rate(gnatsd_varz_out_msgs{job=\"nats\"}[$__rate_interval])",
          "legendFormat": "out",
          "range": true,
          "refId": "B"
        }
      ],
      "title": "NATS messages",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "decimals": 0,
          "max": 1,
          "min": 0,
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 24,
        "x": 0,
        "y": 21
      },
      "id": 10,
      "options": {
        "legend": {
          "calcs": [
            "lastNotNull"
          ],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "up",
          "legendFormat": "{{job}} — {{instance}}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Prometheus targets: 1 = up, 0 = down",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "unit": "reqps"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 0,
        "y": 29
      },
      "id": 11,
      "options": {
        "legend": {
          "calcs": [
            "lastNotNull"
          ],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "sum by (status) (rate(vmsh_http_requests_total{job=\"aiohttp\"}[$__rate_interval]))",
          "legendFormat": "HTTP {{status}}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Backend RPS by status — after deployment",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "unit": "s"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 8,
        "y": 29
      },
      "id": 12,
      "options": {
        "legend": {
          "calcs": [
            "lastNotNull"
          ],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "histogram_quantile(0.95, sum by (le, route) (rate(vmsh_http_request_duration_seconds_bucket{job=\"aiohttp\"}[$__rate_interval])))",
          "legendFormat": "{{route}}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Backend p95 latency by route — after deployment",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "decimals": 2,
          "max": 100,
          "min": 0,
          "unit": "percent"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 16,
        "y": 29
      },
      "id": 13,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto",
        "wideLayout": true
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "100 * sum(rate(vmsh_http_requests_total{job=\"aiohttp\", status=~\"5..\"}[5m])) / clamp_min(sum(rate(vmsh_http_requests_total{job=\"aiohttp\"}[5m])), 0.001)",
          "legendFormat": "5xx",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Backend 5xx share — after deployment",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 37
      },
      "id": 14,
      "options": {
        "legend": {
          "calcs": [
            "lastNotNull"
          ],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "sum by (route) (vmsh_http_requests_in_progress{job=\"aiohttp\"})",
          "legendFormat": "{{route}}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Backend requests in progress — after deployment",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 37
      },
      "id": 15,
      "options": {
        "legend": {
          "calcs": [
            "lastNotNull"
          ],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "sum by (route) (vmsh_websocket_connections{job=\"aiohttp\"})",
          "legendFormat": "{{route}}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "WebSocket connections — after deployment",
      "type": "timeseries"
    }
  ],
  "refresh": "30s",
  "schemaVersion": 41,
  "tags": [
    "vmsh",
    "prometheus"
  ],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-6h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "browser",
  "title": "VMsh server overview",
  "uid": "vmsh-overview",
  "version": 1,
  "weekStart": ""
}
JSON

chown root:grafana \
    /etc/grafana/provisioning/datasources/prometheus.yaml \
    /etc/grafana/provisioning/dashboards/vmsh.yaml

chmod 0640 \
    /etc/grafana/provisioning/datasources/prometheus.yaml \
    /etc/grafana/provisioning/dashboards/vmsh.yaml

chown grafana:grafana /var/lib/grafana/dashboards/vmsh-overview.json
chmod 0640 /var/lib/grafana/dashboards/vmsh-overview.json

GRAFANA_CREDENTIALS_FILE=/root/grafana-admin-credentials.txt

if [[ -s "${GRAFANA_CREDENTIALS_FILE}" ]]; then
    GRAFANA_ADMIN_PASSWORD="$(sed -n 's/^password=//p' "${GRAFANA_CREDENTIALS_FILE}" | head -n 1)"
fi

if [[ -z "${GRAFANA_ADMIN_PASSWORD:-}" ]]; then
    GRAFANA_ADMIN_PASSWORD="Vmsh-$(openssl rand -hex 24)-A9!"
fi

cat > "${GRAFANA_CREDENTIALS_FILE}" <<EOF
url=https://grafvmsh.shashkovs.ru/
username=admin
password=${GRAFANA_ADMIN_PASSWORD}
EOF

chmod 0600 "${GRAFANA_CREDENTIALS_FILE}"

systemctl daemon-reload
systemctl enable grafana-server.service
systemctl restart grafana-server.service

wait_for_grafana || die "Grafana не отвечает на 127.0.0.1:3001."

systemctl stop grafana-server.service

if [[ -x /usr/share/grafana/bin/grafana ]]; then
    runuser -u grafana -- \
        /usr/share/grafana/bin/grafana cli \
        --homepath /usr/share/grafana \
        --config /etc/grafana/grafana.ini \
        --configOverrides cfg:default.paths.data=/var/lib/grafana \
        admin reset-admin-password "${GRAFANA_ADMIN_PASSWORD}"
elif command -v grafana-cli >/dev/null 2>&1; then
    runuser -u grafana -- \
        grafana-cli \
        --homepath /usr/share/grafana \
        --config /etc/grafana/grafana.ini \
        --configOverrides cfg:default.paths.data=/var/lib/grafana \
        admin reset-admin-password "${GRAFANA_ADMIN_PASSWORD}"
else
    die "Не найден Grafana CLI для установки пароля администратора."
fi

systemctl start grafana-server.service
wait_for_grafana || die "Grafana не отвечает после установки пароля администратора."

log "Настройка NGINX reverse proxy для grafvmsh.shashkovs.ru"

backup_once /etc/nginx/conf.d/grafana-websocket-map.conf

cat > /etc/nginx/conf.d/grafana-websocket-map.conf <<'NGINX'
map $http_upgrade $grafana_connection_upgrade {
    default upgrade;
    ''      close;
}
NGINX

backup_once /etc/nginx/sites-available/grafvmsh.shashkovs.ru

cat > /etc/nginx/sites-available/grafvmsh.shashkovs.ru <<'NGINX'
server {
    listen 80;
    listen [::]:80;

    server_name grafvmsh.shashkovs.ru;
    access_log off;

    location / {
        return 404;
    }
}
NGINX

ln -sfn \
    /etc/nginx/sites-available/grafvmsh.shashkovs.ru \
    /etc/nginx/sites-enabled/grafvmsh.shashkovs.ru

nginx -t
systemctl reload nginx

CERTBOT_SUCCEEDED=0

if certbot certonly \
    --nginx \
    --non-interactive \
    --agree-tos \
    --register-unsafely-without-email \
    --keep-until-expiring \
    --cert-name grafvmsh.shashkovs.ru \
    -d grafvmsh.shashkovs.ru; then
    CERTBOT_SUCCEEDED=1
else
    warn "Certbot не смог получить сертификат. Обычно причина — DNS grafvmsh.shashkovs.ru ещё не указывает на сервер или порт 80 недоступен. Установка продолжится; повторный запуск скрипта снова попробует получить сертификат."
fi

if systemctl cat certbot.timer >/dev/null 2>&1; then
    systemctl enable --now certbot.timer
fi

if [[ -s /etc/letsencrypt/live/grafvmsh.shashkovs.ru/fullchain.pem \
   && -s /etc/letsencrypt/live/grafvmsh.shashkovs.ru/privkey.pem \
   && -s /etc/letsencrypt/options-ssl-nginx.conf \
   && -s /etc/letsencrypt/ssl-dhparams.pem ]] \
   && openssl x509 \
       -checkend 0 \
       -noout \
       -in /etc/letsencrypt/live/grafvmsh.shashkovs.ru/fullchain.pem; then

    CERTBOT_SUCCEEDED=1

    cat > /etc/nginx/sites-available/grafvmsh.shashkovs.ru <<'NGINX'
server {
    listen 80;
    listen [::]:80;

    server_name grafvmsh.shashkovs.ru;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;

    server_name grafvmsh.shashkovs.ru;

    ssl_certificate /etc/letsencrypt/live/grafvmsh.shashkovs.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/grafvmsh.shashkovs.ru/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    add_header Strict-Transport-Security "max-age=31536000" always;

    access_log off;
    error_log /var/log/nginx/grafvmsh.error.log warn;

    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $grafana_connection_upgrade;

        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        client_max_body_size 10m;
    }
}
NGINX

    nginx -t
    systemctl reload nginx
else
    CERTBOT_SUCCEEDED=0
fi

log "Ограничение дискового места для journald и NGINX-логов"

mkdir -p /var/log/journal
systemd-tmpfiles --create --prefix /var/log/journal
mkdir -p /etc/systemd/journald.conf.d
backup_once /etc/systemd/journald.conf.d/vmsh-storage-limits.conf

cat > /etc/systemd/journald.conf.d/vmsh-storage-limits.conf <<'INI'
[Journal]
Storage=persistent
SystemMaxUse=512M
SystemKeepFree=1G
SystemMaxFileSize=64M
RuntimeMaxUse=64M
MaxRetentionSec=14day
Compress=yes
INI

systemctl restart systemd-journald
journalctl --vacuum-size=512M >/dev/null || true

backup_once /etc/logrotate.d/nginx

cat > /etc/logrotate.d/nginx <<'LOGROTATE'
/var/log/nginx/*.log {
    hourly
    maxsize 50M
    rotate 5
    missingok
    compress
    delaycompress
    notifempty
    create 0640 www-data adm
    sharedscripts

    postrotate
        if [ -s /run/nginx.pid ]; then
            kill -USR1 "$(cat /run/nginx.pid)"
        fi
    endscript
}
LOGROTATE

mkdir -p /etc/systemd/system/logrotate.timer.d
backup_once /etc/systemd/system/logrotate.timer.d/vmsh-hourly.conf
cat > /etc/systemd/system/logrotate.timer.d/vmsh-hourly.conf <<'UNIT'
[Timer]
OnCalendar=
OnCalendar=hourly
AccuracySec=1m
RandomizedDelaySec=2m
Persistent=true
UNIT

logrotate --debug /etc/logrotate.d/nginx >/dev/null 2>&1
systemctl daemon-reload
systemctl restart logrotate.timer

log "Создание памятки для будущего деплоя aiohttp и Telegram-бота"

cat > /root/monitoring-after-app-deploy.txt <<'TXT'
После деплоя aiohttp-приложения:

1. Приложение должно слушать 127.0.0.1:8000 и отдавать Prometheus-метрики по /metrics.

Встроенный dashboard уже ожидает следующие семейства метрик:

vmsh_http_requests_total{method,route,status}
vmsh_http_request_duration_seconds_bucket{method,route,le}
vmsh_http_requests_in_progress{method,route}
vmsh_websocket_connections{route}

В label route должен попадать шаблон маршрута вроде /api/users/{id}, а не фактический URL.

2. Включить его как Prometheus target:

cat > /etc/prometheus/targets/aiohttp.json <<'JSON'
[
  {
    "targets": ["127.0.0.1:8000"],
    "labels": {
      "instance": "vmsh.shashkovs.ru"
    }
  }
]
JSON

Prometheus увидит изменение автоматически, без restart/reload.

3. В публичном server-блоке NGINX для vmsh.shashkovs.ru закрыть endpoint:

location = /metrics {
    access_log off;
    return 404;
}

4. Если Telegram-бот позднее поднимет отдельный endpoint 127.0.0.1:8001/metrics:

cat > /etc/prometheus/targets/telegram-bot.json <<'JSON'
[
  {
    "targets": ["127.0.0.1:8001"],
    "labels": {
      "instance": "vmsh.shashkovs.ru"
    }
  }
]
JSON

5. Проверка targets:

curl -fsS http://127.0.0.1:9090/api/v1/targets | python3 -m json.tool | less

6. Для Gunicorn с несколькими worker'ами prometheus_client нужно включать в multiprocess mode; нельзя просто использовать обычный глобальный registry каждого worker'а.
TXT

chmod 0600 /root/monitoring-after-app-deploy.txt

log "Финальная проверка конфигурации и сервисов"

runuser -u prometheus -- /usr/local/bin/promtool check config /etc/prometheus/prometheus.yml
nginx -t

wait_for_url http://127.0.0.1:9100/metrics 10 \
    || die "Node Exporter перестал отвечать во время финальной проверки."
wait_for_url http://127.0.0.1:9113/metrics 10 \
    || die "NGINX Exporter перестал отвечать во время финальной проверки."
wait_for_url http://127.0.0.1:7777/metrics 10 \
    || die "NATS Exporter перестал отвечать во время финальной проверки."
wait_for_url http://127.0.0.1:9090/-/ready 10 \
    || die "Prometheus перестал отвечать во время финальной проверки."
wait_for_grafana \
    || die "Grafana перестала отвечать во время финальной проверки."
nats_monitor_healthy \
    || die "NATS monitoring endpoint перестал отвечать во время финальной проверки."
nats_monitor_is_local_only \
    || die "NATS monitoring port 8222 слушает не только loopback-интерфейс."

for service in \
    node_exporter.service \
    nginx-prometheus-exporter.service \
    nats-prometheus-exporter.service \
    prometheus.service \
    grafana-server.service \
    nginx.service; do
    systemctl is-active --quiet "${service}" \
        || die "Сервис ${service} не активен."
done

printf '\nВерсии:\n'
/usr/local/bin/prometheus --version
/usr/local/bin/node_exporter --version 2>&1
/usr/local/bin/nginx-prometheus-exporter --version 2>&1
/usr/local/bin/prometheus-nats-exporter -version 2>&1
/usr/sbin/grafana-server -v 2>/dev/null || true
nginx -v 2>&1

printf '\nЛокальные monitoring-порты (все должны быть привязаны к 127.0.0.1):\n'
ss -H -lntp \
    | awk '$4 ~ /:(3001|7777|8222|9090|9100|9113|18080)$/ {print}' \
    | sort -k4

printf '\nИспользование диска сейчас:\n'
du -sh /var/lib/prometheus /var/lib/grafana /var/log/nginx 2>/dev/null || true
journalctl --disk-usage || true

printf '\n\033[1;32mУстановка завершена.\033[0m\n'
printf 'Grafana: https://grafvmsh.shashkovs.ru/\n'
printf 'Логин и пароль: sudo cat /root/grafana-admin-credentials.txt\n'
printf 'Памятка для будущего приложения: sudo cat /root/monitoring-after-app-deploy.txt\n'
printf 'Prometheus хранит до 60 дней, но не более 2500 MB persisted blocks.\n'
printf 'journald ограничен 512 MB; NGINX-логи ротируются при 50 MB, хранится 5 архивов.\n'

if ((CERTBOT_SUCCEEDED == 0)); then
    printf '\n\033[1;33mGrafana пока не опубликована по HTTPS: сертификат не получен.\033[0m\n'
    printf 'Проверьте DNS A/AAAA для grafvmsh.shashkovs.ru и запустите этот же скрипт повторно.\n'
fi
