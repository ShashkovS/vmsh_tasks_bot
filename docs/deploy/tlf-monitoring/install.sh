#!/usr/bin/env bash
# TLF monitoring scope and rollback: docs/deploy/tlf-monitoring/README.md.
set -Eeuo pipefail
umask 027
[[ $EUID == 0 ]] || { echo 'Run as root.' >&2; exit 1; }
[[ $(hostname) == vmsh-nbg ]] || { echo 'This installer is only for tlfprepagent/vmsh-nbg.' >&2; exit 1; }
SOURCE=$(cd -- "$(dirname -- "$0")" && pwd)
[[ -s /etc/letsencrypt/live/grafprep.leaders.tech/fullchain.pem ]]
openssl x509 -checkend 0 -noout -in /etc/letsencrypt/live/grafprep.leaders.tech/fullchain.pem
FIRST_RUN=0
if [[ ! -f /etc/tlf-monitoring-installed ]]; then
    [[ ${1:-} == --reset-legacy-monitoring ]] || { echo 'First run requires --reset-legacy-monitoring.' >&2; exit 1; }
    FIRST_RUN=1
fi
STAGE=$(mktemp -d /tmp/tlf-monitoring.XXXXXX)
trap 'rm -rf -- "$STAGE"' EXIT
fetch_binary() {
    local name=$1 url=$2 digest=$3
    curl --proto '=https' --tlsv1.2 -fL --retry 3 --max-time 180 "$url" -o "$STAGE/$name.tgz"
    printf '%s  %s\n' "$digest" "$STAGE/$name.tgz" | sha256sum -c --status
    mkdir "$STAGE/$name"
    tar -xzf "$STAGE/$name.tgz" -C "$STAGE/$name"
}
fetch_binary prometheus https://github.com/prometheus/prometheus/releases/download/v3.13.2/prometheus-3.13.2.linux-amd64.tar.gz 0e8c4d46101bd025ea8265e377d2caabc57f488fc1be1c367f37db69ea41be6f
fetch_binary node https://github.com/prometheus/node_exporter/releases/download/v1.12.1/node_exporter-1.12.1.linux-amd64.tar.gz b51d8a76aa2a9156a55d501aca6276fae09e262259a5e4e831d2c2222f084e63
fetch_binary nginx https://github.com/nginx/nginx-prometheus-exporter/releases/download/v1.5.1/nginx-prometheus-exporter_1.5.1_linux_amd64.tar.gz 42ddc7ac31c70021d2a5c10414d473526490769632c1ef430b95d76dd1e3c187
fetch_binary nats https://github.com/nats-io/prometheus-nats-exporter/releases/download/v0.20.1/prometheus-nats-exporter-v0.20.1-linux-x86_64.tar.gz a8798bee71effc2473e48f6b166e63e207a7bb7a7e93ffbb643a1d840607b8ae
# Validate the configuration before stopping any service.
"$STAGE/prometheus/prometheus-3.13.2.linux-amd64/promtool" check config "$SOURCE/prometheus.yml"
BACKUP=/root/tlf-monitoring-backups/$(date -u +%Y%m%dT%H%M%SZ)
install -d -m 0700 "$BACKUP"
paths=()
for path in /etc/prometheus /etc/grafana /etc/nginx /etc/systemd/system/prometheus.service /etc/systemd/system/node_exporter.service /etc/systemd/system/nginx-exporter.service /etc/systemd/system/nginx-prometheus-exporter.service /etc/systemd/system/nats-prometheus-exporter.service /usr/local/bin/prometheus /usr/local/bin/promtool /usr/local/bin/node_exporter /usr/local/bin/nginx-prometheus-exporter /usr/local/bin/prometheus-nats-exporter; do
    [[ ! -e $path ]] || paths+=("${path#/}")
done
tar -C / -czf "$BACKUP/configuration-and-binaries.tgz" "${paths[@]}"
systemctl list-units --state=running --type=service --no-legend > "$BACKUP/running-services.before.txt"
systemctl stop grafana-server prometheus node_exporter nginx-exporter
systemctl disable nginx-exporter
if (( FIRST_RUN )); then
    mv /var/lib/prometheus "$BACKUP/prometheus-data"
    for path in /var/lib/grafana/grafana.db /var/lib/grafana/grafana.db-wal /var/lib/grafana/grafana.db-shm; do
        [[ ! -e $path ]] || mv "$path" "$BACKUP/"
    done
    mv /etc/grafana/provisioning "$BACKUP/grafana-provisioning"
    [[ ! -d /var/lib/grafana/dashboards ]] || mv /var/lib/grafana/dashboards "$BACKUP/grafana-dashboards"
fi
for user in prometheus node_exporter nginx_exporter nats_exporter; do
    getent group "$user" >/dev/null || groupadd --system "$user"
    id "$user" >/dev/null 2>&1 || useradd --system --gid "$user" --no-create-home --shell /usr/sbin/nologin "$user"
done
for pair in 'prometheus prometheus' 'prometheus promtool' 'node node_exporter' 'nginx nginx-prometheus-exporter' 'nats prometheus-nats-exporter'; do
    read -r archive binary <<< "$pair"
    file=$(find "$STAGE/$archive" -type f -name "$binary" -print -quit)
    [[ -n $file ]]
    install -o root -g root -m 0755 "$file" "/usr/local/bin/$binary"
done
install -d -o prometheus -g prometheus -m 0750 /var/lib/prometheus
install -d -o root -g prometheus -m 0750 /etc/prometheus /etc/prometheus/targets
install -o root -g prometheus -m 0640 "$SOURCE/prometheus.yml" /etc/prometheus/prometheus.yml
for target in aiohttp telegram-bot nats; do
    if [[ ! -f /etc/prometheus/targets/$target.json ]]; then
        printf '[]\n' > "/etc/prometheus/targets/$target.json"
    fi
    chown root:prometheus "/etc/prometheus/targets/$target.json"
    chmod 0640 "/etc/prometheus/targets/$target.json"
done
for service in prometheus node_exporter nginx-prometheus-exporter nats-prometheus-exporter; do
    install -o root -g root -m 0644 "$SOURCE/$service.service" "/etc/systemd/system/$service.service"
done
install -d -o root -g grafana -m 0750 /etc/grafana/provisioning /etc/grafana/provisioning/datasources /etc/grafana/provisioning/dashboards /etc/grafana/provisioning/alerting /etc/grafana/provisioning/plugins /etc/grafana/provisioning/access-control
install -d -o grafana -g grafana -m 0750 /var/lib/grafana/dashboards
install -o root -g grafana -m 0640 "$SOURCE/grafana.ini" /etc/grafana/grafana.ini
install -o root -g grafana -m 0640 "$SOURCE/datasource.yaml" /etc/grafana/provisioning/datasources/prometheus.yaml
install -o root -g grafana -m 0640 "$SOURCE/dashboards.yaml" /etc/grafana/provisioning/dashboards/tlf.yaml
install -o root -g grafana -m 0640 "$SOURCE/overview.json" /var/lib/grafana/dashboards/tlf-prep-overview.json
if (( FIRST_RUN )); then
    openssl rand -hex 32 > /etc/grafana/secret_key
    openssl rand -hex 32 > /etc/grafana/admin_password
    chown root:grafana /etc/grafana/secret_key /etc/grafana/admin_password
    chmod 0640 /etc/grafana/secret_key /etc/grafana/admin_password
    {
        printf 'url=https://grafprep.leaders.tech/\nusername=admin\npassword='
        cat /etc/grafana/admin_password
    } > /root/grafprep-admin-credentials.txt
    chmod 0600 /root/grafprep-admin-credentials.txt
fi
install -o root -g root -m 0644 "$SOURCE/stub-status.conf" /etc/nginx/conf.d/tlf-prometheus-stub-status.conf
install -o root -g root -m 0644 "$SOURCE/websocket-map.conf" /etc/nginx/conf.d/tlf-grafana-websocket-map.conf
install -o root -g root -m 0644 "$SOURCE/grafprep.nginx.conf" /etc/nginx/sites-available/grafprep.leaders.tech
# The owner authorized replacement of the old monitoring endpoint only.
rm -f /etc/nginx/sites-enabled/grafhezger.shashkovs.ru
ln -sfn /etc/nginx/sites-available/grafprep.leaders.tech /etc/nginx/sites-enabled/grafprep.leaders.tech
nginx -t
systemd-analyze verify /etc/systemd/system/prometheus.service /etc/systemd/system/node_exporter.service /etc/systemd/system/nginx-prometheus-exporter.service
systemctl daemon-reload
systemctl reload nginx
systemctl enable --now prometheus node_exporter nginx-prometheus-exporter grafana-server
wait_url() {
    local url=$1
    for ((i=0;i<60;i++)); do
        if curl -fsS --max-time 2 -H 'Host: grafprep.leaders.tech' "$url" >/dev/null; then return; fi
        sleep 1
    done
    return 1
}
wait_url http://127.0.0.1:9090/-/ready
wait_url http://127.0.0.1:3001/api/health
wait_url http://127.0.0.1:9100/metrics
wait_url http://127.0.0.1:9113/metrics
printf 'Installed from %s\nBackup: %s\n' "$SOURCE" "$BACKUP" > /etc/tlf-monitoring-installed
systemctl list-units --state=running --type=service --no-legend > "$BACKUP/running-services.after.txt"
printf 'Monitoring ready. Backup: %s\nAdmin credentials: /root/grafprep-admin-credentials.txt\n' "$BACKUP"
