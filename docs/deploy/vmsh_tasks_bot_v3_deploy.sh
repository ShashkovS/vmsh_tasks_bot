ssh -F C:\Users\sh57\.ssh\config root@217.114.6.190 -p 22 -i "C:\Users\sh57\.ssh\id_ed25519"

# BMFdPmQ9%Ncc

sudo apt-get update
sudo apt-get upgrade
sudo apt-get dist-upgrade
sudo apt update -y && sudo apt full-upgrade -y && sudo apt autoremove -y && sudo apt clean -y && sudo apt autoclean -y
sudo apt install unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades


sudo useradd -m -p $(openssl passwd -1 'YT82S6TYtcWEsKeU49RV') serge
# sudo passwd serge
usermod -aG sudo serge

mkdir -p /home/serge/.ssh && touch /home/serge/.ssh/authorized_keys
nano /home/serge/.ssh/authorized_keys
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIzDfZZY6oBW4V8EBZUfdfc/2ye9isNWubpG/TTSs/qy sergeyshashkov@admins-MacBook-Air-2.local
chmod 700 /home/serge/.ssh && chmod 600 /home/serge/.ssh/authorized_keys
chown -R serge:serge /home/serge/.ssh

# Проверяем коннект
ssh serge@217.114.6.190 -p 22 -i "C:\Users\sh57\.ssh\id_ed25519"



# Настраиваем файрволы
sudo apt install -y fail2ban ufw fish ripgrep
printf "[sshd]\nenabled = true\nbanaction = iptables-multiport" > /etc/fail2ban/jail.local
systemctl enable fail2ban
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
sed -i -e '/^\(#\|\)PermitRootLogin/s/^.*$/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i -e '/^\(#\|\)PasswordAuthentication/s/^.*$/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i -e '/^\(#\|\)PubkeyAuthentication/s/^.*$/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sed -i -e '/^\(#\|\)KbdInteractiveAuthentication/s/^.*$/KbdInteractiveAuthentication no/' /etc/ssh/sshd_config
sed -i -e '/^\(#\|\)ChallengeResponseAuthentication/s/^.*$/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config
sed -i -e '/^\(#\|\)MaxAuthTries/s/^.*$/MaxAuthTries 2/' /etc/ssh/sshd_config
sed -i -e '/^\(#\|\)AllowTcpForwarding/s/^.*$/AllowTcpForwarding no/' /etc/ssh/sshd_config
sed -i -e '/^\(#\|\)X11Forwarding/s/^.*$/X11Forwarding no/' /etc/ssh/sshd_config
sed -i -e '/^\(#\|\)AllowAgentForwarding/s/^.*$/AllowAgentForwarding no/' /etc/ssh/sshd_config
sed -i -e '/^\(#\|\)AuthorizedKeysFile/s/^.*$/AuthorizedKeysFile .ssh\/authorized_keys/' /etc/ssh/sshd_config
#sed -i '$a AllowUsers serge' /etc/ssh/sshd_config
#sed -i '$a AllowGroups web' /etc/ssh/sshd_config
sed -i -e '/^\(#\|\)Port/s/^.*$/Port 22179/' /etc/ssh/sshd_config
# Проверяем валидность
sudo sshd -t
# Смотрим, что получилось
sudo sshd -T | egrep -i 'allowusers|passwordauth|permitroot|allowgroups'

# Включаем файрвол
sudo ufw allow 22179/tcp comment 'Allow SSH'
sudo ufw allow 80 comment 'web'
sudo ufw allow 443 comment 'web'
sudo ufw enable


# Перезапускаем ssh
sudo systemctl restart ssh.socket
# Проверяем порты SSH-сервера:
sudo systemctl status ssh
sudo ss -tupln | grep ssh

# Работает новый конфиг?
ssh -F C:\Users\sh57\.ssh\config serge@217.114.6.190 -p 22179 -i "C:\Users\sh57\.ssh\id_ed25519"

# ребутимся
reboot

# Ставим fish
whereis fish
chsh -s /usr/bin/fish

# Разрешаем sudo без пароля
EDITOR=nano sudo -E visudo


# ==============================


# установка пачки всего
sudo apt-get update
sudo apt-get upgrade
sudo apt -y install gcc-15 mc nano p7zip-full libxi-dev libxerces-c-dev libspdlog-dev libuchardet-dev libssh-dev libssl-dev libsmbclient-dev libnfs-dev libneon27-dev libarchive-dev cmake g++ git curl wget
sudo apt -y install python3 python3-dev python3-pip python3-full git wget unzip acl build-essential libssl-dev libffi-dev

# для ejudge
sudo apt install -y net-tools wget tar p7zip htop make gcc bison   sed file expat libzip-dev libcurl4-openssl-dev openssl git tmux  gcc g++ locales-all   zip libzip-dev uuid uuid-dev vim screen wget mc gcc strace subversion gdb autoconf automake clang
sudo apt install -y fcgiwrap spawn-fcgi

# nginx, certbot
sudo apt install -y snapd nginx
sudo snap install core& sudo snap refresh core
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot

# rsync, far
sudo apt install  -y rsync
sudo apt install  -y far2l



# chrome
cd ~
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb



# =======
# nats
# Устанавливаем golang и nats
set -euo pipefail

GO_VERSION="1.26.5"
NATS_VERSION="2.14.3"
ARCH="$(dpkg --print-architecture)"

case "${ARCH}" in
    amd64)
        GO_ARCH="amd64"
        GO_SHA256="5c2c3b16caefa1d968a94c1daca04a7ca301a496d9b086e17ad77bb81393f053"
        NATS_ARCH="amd64"
        NATS_SHA256="e0c053fc2abe991f17b2be794897bb3f94ca1857bf886498c741ba69fb62522a"
        ;;
    arm64)
        GO_ARCH="arm64"
        GO_SHA256="fe4789e92b1f33358680864bbe8704289e7bb5fc207d80623c308935bd696d49"
        NATS_ARCH="arm64"
        NATS_SHA256="9fb1d20a62268e82fe4fe3b3817ac61a4b6de45278aee7881d43f3e40966a92c"
        ;;
    *)
        echo "Неподдерживаемая архитектура: ${ARCH}" >&2
        exit 1
        ;;
esac

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates \
    curl

GO_ARCHIVE="go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
NATS_PACKAGE="nats-server-v${NATS_VERSION}-${NATS_ARCH}.deb"

curl -fL --retry 5 --retry-delay 2 \
    -o "/tmp/${GO_ARCHIVE}" \
    "https://go.dev/dl/${GO_ARCHIVE}"

echo "${GO_SHA256}  /tmp/${GO_ARCHIVE}" | sha256sum --check

rm -rf /usr/local/go
tar -C /usr/local -xzf "/tmp/${GO_ARCHIVE}"

cat >/etc/profile.d/golang.sh <<'EOF'
export PATH="/usr/local/go/bin:${PATH}"
EOF

chmod 0644 /etc/profile.d/golang.sh

export PATH="/usr/local/go/bin:${PATH}"

go version
gofmt -h >/dev/null

curl -fL --retry 5 --retry-delay 2 \
    -o "/tmp/${NATS_PACKAGE}" \
    "https://github.com/nats-io/nats-server/releases/download/v${NATS_VERSION}/${NATS_PACKAGE}"

echo "${NATS_SHA256}  /tmp/${NATS_PACKAGE}" | sha256sum --check

dpkg -i "/tmp/${NATS_PACKAGE}"

nats-server --version


if getent group nats >/dev/null; then
    true
else
    groupadd --system nats
fi

if id nats >/dev/null 2>&1; then
    usermod \
        --home /var/lib/nats \
        --shell /usr/sbin/nologin \
        nats
else
    useradd \
        --system \
        --gid nats \
        --home-dir /var/lib/nats \
        --no-create-home \
        --shell /usr/sbin/nologin \
        nats
fi

install -d -o root -g nats -m 0750 /etc/nats
install -d -o nats -g nats -m 0750 /var/lib/nats

SERVER_NAME="$(hostname -s)"

cat >/etc/nats/nats-server.conf <<EOF
server_name: "${SERVER_NAME}"

listen: "127.0.0.1:4222"
http: "127.0.0.1:8222"

lame_duck_grace_period: "2s"
lame_duck_duration: "30s"
EOF

chown root:nats /etc/nats/nats-server.conf
chmod 0640 /etc/nats/nats-server.conf

sudo -u nats /usr/bin/nats-server \
    -t \
    -c /etc/nats/nats-server.conf



cat >/etc/systemd/system/nats-server.service <<'EOF'
[Unit]
Description=NATS Server
Documentation=https://docs.nats.io/
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=nats
Group=nats

ExecStartPre=/usr/bin/nats-server -t -c /etc/nats/nats-server.conf
ExecStart=/usr/bin/nats-server -c /etc/nats/nats-server.conf
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s SIGUSR2 $MAINPID

Restart=on-failure
RestartSec=5s
TimeoutStopSec=30s

LimitNOFILE=800000
UMask=0077

StateDirectory=nats
StateDirectoryMode=0750

NoNewPrivileges=true
PrivateDevices=true
PrivateTmp=true
PrivateIPC=true

CapabilityBoundingSet=
LockPersonality=true
MemoryDenyWriteExecute=true

ProtectClock=true
ProtectControlGroups=true
ProtectHome=true
ProtectHostname=true
ProtectKernelLogs=true
ProtectKernelModules=true
ProtectKernelTunables=true
ProtectSystem=strict
ProtectProc=invisible
ProcSubset=pid

RestrictAddressFamilies=AF_INET AF_INET6
RestrictNamespaces=true
RestrictRealtime=true
RestrictSUIDSGID=true

SystemCallArchitectures=native
SystemCallFilter=@system-service ~@privileged ~@resources

ReadWritePaths=/var/lib/nats
InaccessiblePaths=/etc/ssh

[Install]
WantedBy=multi-user.target
EOF

systemd-analyze verify /etc/systemd/system/nats-server.service

systemctl daemon-reload
systemctl enable --now nats-server.service




systemctl status nats-server.service --no-pager
journalctl -u nats-server.service -n 100 --no-pager

ss -ltnp | grep -E ':(4222|8222)[[:space:]]'

curl -fsS http://127.0.0.1:8222/varz



# ==============================================
# Настраиваем nginx

sudo useradd -r -s /sbin/nologin nginx
sudo nano /etc/nginx/nginx.conf
# user nginx nginx
sudo usermod -a -G www-data nginx
sudo nginx -t
# Перезапускаем nginx
sudo nginx -s stop
sudo systemctl enable nginx
sudo systemctl start nginx
# сертификат
sudo apt install openssl
sudo mkdir -p /etc/pki/nginx
sudo openssl dhparam -out /etc/pki/nginx/dhparam.pem 4096


# nodejs
sudo apt install nodejs npm  -y
# pnpm
curl -fsSL https://get.pnpm.io/install.sh | sh -


# ==============================================
# Настраиваем папку вебпроектов
sudo useradd web --create-home --user-group --shell /bin/false
sudo usermod -a -G web nginx
sudo usermod -a -G web serge
sudo mkdir /web
sudo chown web:web /web
sudo chmod 2770 /web










# =================================================
# Prometheus + Grafana + Node Exporter
# ref docs/deploy/install_vmsh_monitoring_beget.sh

sudo useradd --no-create-home --shell /bin/false prometheus
sudo mkdir /etc/prometheus
sudo mkdir /var/lib/prometheus
cd /tmp
wget https://github.com/prometheus/prometheus/releases/download/v2.54.1/prometheus-2.54.1.linux-amd64.tar.gz
tar -xvf prometheus-2.54.1.linux-amd64.tar.gz
cd prometheus-2.54.1.linux-amd64
sudo cp prometheus /usr/local/bin/
sudo cp promtool /usr/local/bin/
sudo cp -r consoles /etc/prometheus
sudo cp -r console_libraries /etc/prometheus
sudo cp prometheus.yml /etc/prometheus/
sudo mkdir -p /var/lib/prometheus/
sudo chown -R prometheus:prometheus /var/lib/prometheus/
sudo chmod -R 775 /var/lib/prometheus/



sudo nano /etc/prometheus/prometheus.yml

sudo nano /etc/systemd/system/prometheus.service

[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus --config.file /etc/prometheus/prometheus.yml --storage.tsdb.path /var/lib/prometheus/ --web.console.templates=/etc/prometheus/consoles --web.console.libraries=/etc/prometheus/console_libraries

[Install]
WantedBy=multi-user.target


sudo systemctl daemon-reload
sudo systemctl start prometheus
sudo systemctl enable prometheus
sudo systemctl restart prometheus
sudo systemctl status prometheus
sudo journalctl -u journalclt --since "5 minutes ago"


sudo nano /etc/prometheus/prometheus.yml

scrape_configs:
  - job_name: 'node_exporter'
    static_configs:
      - targets: ['localhost:9100']

sudo systemctl restart prometheus
sudo systemctl status prometheus


#============= grafana
sudo apt-get install -y apt-transport-https software-properties-common wget
sudo mkdir -p /etc/apt/keyrings/
wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor | sudo tee /etc/apt/keyrings/grafana.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list
sudo apt-get update
sudo apt-get install grafana


sudo useradd -r -s /sbin/nologin grafana
# sudo usermod -a -G groupName userName
sudo usermod -a -G grafana serge
sudo usermod -a -G web grafana
sudo usermod -a -G grafana nginx

mkdir /web/grafana
sudo chown -R grafana:grafana /web/grafana



sudo systemctl stop grafana-server
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
sudo systemctl status grafana-server

sudo nano /etc/grafana/grafana.ini
	protocol = https
	http_addr = 127.0.0.1
	http_port = 3001
	socket = /web/grafana/grafana.sock
# Задайте права на Unix-сокет
socket_permissions = 0660
/web/grafana/grafana.sock

sudo systemctl restart grafana-server
sudo systemctl status grafana-server

sudo certbot certonly --nginx -d grafvmsh.shashkovs.ru

sudo nano /etc/nginx/sites-available/grafvmsh.shashkovs.ru

    server {
        listen [::]:443 ssl http2; # managed by Certbot
        listen 443 ssl http2; # managed by Certbot
        server_name grafvmsh.shashkovs.ru; # managed by Certbot

        ssl_certificate /etc/letsencrypt/live/grafvmsh.shashkovs.ru/fullchain.pem; # managed by Certbot
        ssl_certificate_key /etc/letsencrypt/live/grafvmsh.shashkovs.ru/privkey.pem; # managed by Certbot
        include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
        ssl_dhparam /etc/pki/nginx/dhparam.pem;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

        location / {
          proxy_pass http://unix:/web/grafana/grafana.sock;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

sudo ln -s /etc/nginx/sites-available/grafvmsh.shashkovs.ru /etc/nginx/sites-enabled/

sudo nginx -t
sudo systemctl reload nginx

https://grafvmsh.shashkovs.ru/login
`admin` `GpfKCudDMcg8ABLw45`







# Установка Node Exporter
cd ~
wget https://github.com/prometheus/node_exporter/releases/download/v1.8.2/node_exporter-1.8.2.linux-amd64.tar.gz
tar xvfz node_exporter-1.8.2.linux-amd64.tar.gz
sudo cp node_exporter-1.8.2.linux-amd64/node_exporter /usr/local/bin/

sudo nano /etc/systemd/system/node_exporter.service

[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=root
Group=root
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target


sudo systemctl daemon-reload
sudo systemctl start node_exporter
sudo systemctl enable node_exporter
sudo systemctl status node_exporter


sudo nano /etc/prometheus/prometheus.yml

scrape_configs:
  - job_name: 'node_exporter'
    static_configs:
      - targets: ['localhost:9100']

sudo systemctl restart prometheus
sudo systemctl status node_exporter



# NGINX Prometheus Exporter

cd ~
wget https://github.com/nginxinc/nginx-prometheus-exporter/releases/download/v1.3.0/nginx-prometheus-exporter_1.3.0_linux_amd64.tar.gz
tar xvf nginx-prometheus-exporter_1.3.0_linux_amd64.tar.gz
sudo mv nginx-prometheus-exporter /usr/local/bin/

sudo nano /etc/systemd/system/nginx-exporter.service


[Unit]
Description=Nginx Exporter
After=network.target

[Service]
ExecStart=/usr/local/bin/nginx-prometheus-exporter -nginx.scrape-uri=http://127.0.0.1:8080/stub_status

[Install]
WantedBy=multi-user.target


sudo systemctl daemon-reload
sudo systemctl start nginx-exporter
sudo systemctl enable nginx-exporter
sudo systemctl status nginx-exporter



sudo nano /etc/nginx/conf.d/stats.conf
server {
    listen 8080;
    server_name localhost;

    location /stub_status {
        stub_status on;
        access_log off;
        allow 127.0.0.1;
        deny all;
    }
}


sudo nginx -t
sudo systemctl reload nginx


curl http://127.0.0.1:8080/stub_status

sudo setfacl -R -m u:nginx:rX /etc/letsencrypt/{live,archive}

sudo nano /etc/prometheus/prometheus.yml

global:
  scrape_interval: 5s # Интервал сбора метрик
  evaluation_interval: 5s # Интервал оценки правил

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node_exporter'
    static_configs:
      - targets: ['localhost:9100']

  - job_name: 'nginx_exporter'
    static_configs:
      - targets: ['localhost:9113'] # предполагаемый порт NGINX Exporter


sudo systemctl restart prometheus
sudo systemctl status prometheus
























# Настраиваем dns для нового поддомена
# ...

# Настраиваем ssl для нового поддомена
sudo certbot certonly --nginx -d vmsh.shashkovs.ru
   # /etc/letsencrypt/live/vmsh.shashkovs.ru/fullchain.pem
   # Your key file has been saved at:
   # /etc/letsencrypt/live/vmsh.shashkovs.ru/privkey.pem


# Содержимое каждого сайта будет находиться в собственном каталоге, поэтому создаём нового пользователя
sudo useradd vmsh_tasks_bot -m -U -s /bin/false
mkdir /web/vmsh_tasks_bot


# Делаем каталоги для данных сайта (файлы сайта, логи и временные файлы):
sudo mkdir -p -m 754 /web/vmsh_tasks_bot/logs
sudo mkdir -p -m 777 /web/vmsh_tasks_bot/tmp

# Делаем юзера и его группу владельцем  всех своих папок
sudo chown -R vmsh_tasks_bot:vmsh_tasks_bot /web/vmsh_tasks_bot
# Делаем так, чтобы всё новое лежало в группе
# Изменяем права доступа на каталог
sudo chmod  2770 /web/vmsh_tasks_bot

# Чтобы Nginx получил доступ к файлам сайта, добавим пользователя nginx в группу
sudo usermod -a -G vmsh_tasks_bot nginx
sudo usermod -a -G vmsh_tasks_bot serge
sudo usermod -a -G vmsh_tasks_bot root
sudo usermod -a -G web vmsh_tasks_bot
sudo usermod -a -G vmsh_tasks_bot web



sudo chgrp -R vmsh_tasks_bot /web/vmsh_tasks_bot
sudo chmod 2770 /web/vmsh_tasks_bot
sudo find /web/vmsh_tasks_bot -type d -exec chmod 2770 '{}' \;
sudo setfacl -R -d -m group:vmsh_tasks_bot:rwx /web/vmsh_tasks_bot
sudo setfacl -R -m group:vmsh_tasks_bot:rwx /web/vmsh_tasks_bot
# sudo chmod -R ug+rwX,o-wx /web/vmsh_tasks_bot
# sudo chmod -R ug-s /web/vmsh_tasks_bot


# Клонируем репу
sudo su vmsh_tasks_bot -s /usr/bin/bash
cd /web/vmsh_tasks_bot
git clone https://github.com/ShashkovS/vmsh_tasks_bot vmsh_tasks_bot

# виртуальное окружение
# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
cd /web/vmsh_tasks_bot/vmsh_tasks_bot
git checkout vmshpwa
git pull
uv sync


# pnpm
curl -fsSL https://get.pnpm.io/install.sh | sh -
pnpm self-update next-12
cd /web/vmsh_tasks_bot/vmsh_tasks_bot/vmshpwa

# nvm
export NVM_DIR="$HOME/.nvm"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.6/install.sh | bash
fi
. "$NVM_DIR/nvm.sh"


# папочки для деплоя
sudo install -d \
  -o vmsh_tasks_bot \
  -g vmsh_tasks_bot \
  -m 2770 \
  /web/vmsh_tasks_bot/vmshpwa \
  /web/vmsh_tasks_bot/vmshpwa/reports

nvm install 26.5.1
nvm alias default 26.5.1
nvm use 26.5.1

export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use --silent 26.5.1

export PNPM_HOME="$HOME/.local/share/pnpm"
export PATH="$PNPM_HOME:$PATH"
export XDG_CACHE_HOME="$HOME/.cache"

cd /web/vmsh_tasks_bot/vmsh_tasks_bot/vmshpwa

CI=true pnpm install \
  --frozen-lockfile \
  --prefer-offline \
  --reporter=append-only
'


sudo -H -u vmsh_tasks_bot bash -lc '
set -euo pipefail

export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use --silent 26.5.1

export PNPM_HOME="$HOME/.local/share/pnpm"
export PATH="$PNPM_HOME:$PATH"
export XDG_CACHE_HOME="$HOME/.cache"
export NODE_OPTIONS="--max-old-space-size=4096"

REPO=/web/vmsh_tasks_bot/vmsh_tasks_bot
RELEASE_ROOT=/web/vmsh_tasks_bot/vmshpwa
REPORT_ROOT="$RELEASE_ROOT/reports"

PUBLIC_MEDIA_ORIGIN="https://s3.ru1.storage.beget.cloud"
SENTRY_DSN="https://09d20146c8b808c3760a240956fb3c90@o489435.ingest.us.sentry.io/4511885728088064"

cd "$REPO"

RELEASE_ID="$(git rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"

make pwa-production-build \
  PWA_RELEASE_ID="$RELEASE_ID" \
  VITE_PUBLIC_MEDIA_ORIGIN="$PUBLIC_MEDIA_ORIGIN" \
  VITE_SENTRY_DSN="$SENTRY_DSN"

make pwa-phase11-release-package \
  PWA_RELEASE_ID="$RELEASE_ID" \
  PWA_RELEASE_ROOT="$RELEASE_ROOT" \
  PWA_RELEASE_REPORT="$REPORT_ROOT/$RELEASE_ID-package.json"

make pwa-phase11-release-verify \
  PWA_RELEASE_ID="$RELEASE_ID" \
  PWA_RELEASE_ROOT="$RELEASE_ROOT" \
  PWA_RELEASE_REPORT="$REPORT_ROOT/$RELEASE_ID-verify.json"

echo
echo "Собран релиз: $RELEASE_ID"
echo "Файлы: $RELEASE_ROOT/$RELEASE_ID"
'



sudo -H -u vmsh_tasks_bot bash -lc '
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

REPO=/web/vmsh_tasks_bot/vmsh_tasks_bot
RELEASE_ROOT=/web/vmsh_tasks_bot/vmshpwa
REPORT_ROOT="$RELEASE_ROOT/reports"

cd "$REPO"

read -r -p "Release ID: " RELEASE_ID

make pwa-phase11-release-activate \
  PWA_RELEASE_ID="$RELEASE_ID" \
  PWA_RELEASE_ROOT="$RELEASE_ROOT" \
  PWA_RELEASE_REPORT="$REPORT_ROOT/$RELEASE_ID-activate.json"

readlink -f "$RELEASE_ROOT/current"
'
'


# Специальный пользователь для загрузки db
# Создаём restricted bash
sudo ln -s /bin/bash /bin/rbash
sudo useradd vmsh_tasks_botdb -m -U
# sudo su - vmsh_tasks_botdb
sudo mkdir ~vmsh_tasks_botdb/.ssh
sudo chmod 700 ~/.ssh
sudo ssh-keygen -t ed25519 -C "vmsh_tasks_botdb@vmsh.shashkovs.ru"
 # /home/vmsh_tasks_botdb/.ssh/id_ed25519_backup
sudo touch ~vmsh_tasks_botdb/.ssh/authorized_keys
sudo chmod 600 ~vmsh_tasks_botdb/.ssh/authorized_keys
sudo cat ~vmsh_tasks_botdb/.ssh/id_ed25519_backup.pub >> ~vmsh_tasks_botdb/.ssh/authorized_keys
sudo cat ~vmsh_tasks_botdb/.ssh/id_ed25519_backup
-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
exit
sudo chown vmsh_tasks_botdb:vmsh_tasks_botdb ~vmsh_tasks_botdb/.ssh
sudo usermod -a -G vmsh_tasks_bot vmsh_tasks_botdb

# Создаём папку для разрешённых бинарников (yourestricteduser — имя вашего пользователя)
sudo mkdir /home/vmsh_tasks_botdb/bin
# Создаём ссылку на команду ls, чтобы её разрешить
sudo ln -s /usr/bin/ls /home/vmsh_tasks_botdb/bin/ls
sudo ln -s /usr/bin/7za /home/vmsh_tasks_botdb/bin/7za
sudo ln -s /usr/bin/sqlite3 /home/vmsh_tasks_botdb/bin/sqlite3
sudo ln -s /usr/bin/rm /home/vmsh_tasks_botdb/bin/rm
sudo ln -s /web/vmsh_tasks_bot/vmsh_tasks_bot/db ~vmsh_tasks_botdb/db
sudo chown vmsh_tasks_botdb:vmsh_tasks_botdb ~vmsh_tasks_botdb/db
# Ставим restricted bash при запуске
sudo chsh -s /bin/rbash vmsh_tasks_botdb
# Настройка при логине
echo 'export PATH=$HOME/bin' | sudo tee /home/vmsh_tasks_botdb/.bash_profile

ssh vmsh_tasks_botdb@188.245.158.162 -p 22179 -i "X:\Dropbox\ВМШ 5-7 2024-2025\Py_VMSH_5-7_2024\db\_vmsh_tasks_botdb.priv.ppk"






# Делаем юзера и его группу владельцем  всех своих папок
sudo chown -R vmsh_tasks_bot:vmsh_tasks_bot /web/vmsh_tasks_bot
# Делаем так, чтобы всё новое лежало в группе





# Настраиваем systemd для поддержания приложения в рабочем состоянии
# Начинаем с описания сервиса
echo '
[Unit]
Description=Gunicorn instance to serve vmsh_tasks_bot
After=network.target

[Service]
PIDFile=/web/vmsh_tasks_bot/vmsh_tasks_bot.pid
Restart=always
RestartSec=0
User=vmsh_tasks_bot
Group=nginx
RuntimeDirectory=gunicorn
WorkingDirectory=/web/vmsh_tasks_bot/vmsh_tasks_bot
Environment="PATH=/web/vmsh_tasks_bot/vmsh_tasks_bot/.venv/bin"
Environment="PROD=true"
Environment="LD_RUN_PATH=/usr/local/lib"
Environment="LD_LIBRARY_PATH=/usr/local/lib"
ExecStart=/web/vmsh_tasks_bot/vmsh_tasks_bot/.venv/bin/gunicorn  --pid /web/vmsh_tasks_bot/vmsh_tasks_bot.pid  --workers 2  --bind unix:/web/vmsh_tasks_bot/vmsh_tasks_bot.socket --worker-class aiohttp.GunicornUVLoopWebWorker -m 007  main:app
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s TERM $MAINPID
PrivateTmp=true

[Install]
WantedBy=multi-user.target
' > /web/vmsh_tasks_bot/gunicorn.vmsh_tasks_bot.service
sudo ln -s /web/vmsh_tasks_bot/gunicorn.vmsh_tasks_bot.service /etc/systemd/system/gunicorn.vmsh_tasks_bot.service

# Тестовый запуск
cd /web/vmsh_tasks_bot/vmsh_tasks_bot && export PROD=true && /web/vmsh_tasks_bot/vmsh_tasks_bot/.venv/bin/gunicorn  --pid /web/vmsh_tasks_bot/vmsh_tasks_bot.pid  --workers 2  --bind unix:/web/vmsh_tasks_bot/vmsh_tasks_bot.socket --worker-class aiohttp.GunicornUVLoopWebWorker -m 007  main:app


# ставим свежайший nginx с поддержкой brotli
set -euo pipefail
STAMP="$(date +%Y%m%d-%H%M%S)"
sudo cp -a /etc/nginx "/root/nginx-backup-${STAMP}"
sudo nginx -T 2>&1 | sudo tee "/root/nginx-T-${STAMP}.txt" >/dev/null
nginx -V 2>&1 | sudo tee "/root/nginx-V-${STAMP}.txt"

sudo apt update

sudo apt install -y \
    curl \
    gnupg2 \
    ca-certificates \
    lsb-release \
    ubuntu-keyring

curl -fsSL https://nginx.org/keys/nginx_signing.key \
    | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null

gpg --dry-run --quiet --no-keyring \
    --import \
    --import-options import-show \
    /usr/share/keyrings/nginx-archive-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] https://nginx.org/packages/mainline/ubuntu $(lsb_release -cs) nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list

printf 'Package: *\nPin: origin nginx.org\nPin: release o=nginx\nPin-Priority: 900\n' \
    | sudo tee /etc/apt/preferences.d/99nginx

sudo apt update

apt-cache policy nginx

sudo apt-get install -y \
    -o Dpkg::Options::="--force-confold" \
    nginx

nginx -v
sudo nginx -t

# brotli
sudo apt install -y \
    git \
    build-essential \
    cmake \
    libpcre2-dev \
    zlib1g-dev \
    libssl-dev

set -euo pipefail

NGINX_VERSION="$(nginx -v 2>&1 | sed 's#nginx version: nginx/##')"
BUILD_DIR="$(mktemp -d /tmp/nginx-brotli.XXXXXX)"

echo "Building Brotli for nginx ${NGINX_VERSION}"
echo "Build directory: ${BUILD_DIR}"

git clone \
    --recurse-submodules \
    --shallow-submodules \
    --depth 1 \
    https://github.com/google/ngx_brotli.git \
    "${BUILD_DIR}/ngx_brotli"

cmake \
    -S "${BUILD_DIR}/ngx_brotli/deps/brotli" \
    -B "${BUILD_DIR}/ngx_brotli/deps/brotli/out" \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF

cmake \
    --build "${BUILD_DIR}/ngx_brotli/deps/brotli/out" \
    --config Release \
    --target brotlienc \
    --parallel "$(nproc)"

cd "${BUILD_DIR}"

curl -fsSLO \
    "https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz"

tar xzf "nginx-${NGINX_VERSION}.tar.gz"

cd "nginx-${NGINX_VERSION}"

CONFIGURE_ARGS="$(nginx -V 2>&1 | sed -n 's/^configure arguments: //p')"

if [[ " ${CONFIGURE_ARGS} " != *" --with-compat "* ]]; then
    CONFIGURE_ARGS="${CONFIGURE_ARGS} --with-compat"
fi

eval "./configure ${CONFIGURE_ARGS} --add-dynamic-module=${BUILD_DIR}/ngx_brotli"

make -j"$(nproc)" modules

sudo install -d -m 0755 /usr/lib/nginx/modules

sudo install -m 0644 \
    objs/ngx_http_brotli_filter_module.so \
    /usr/lib/nginx/modules/ngx_http_brotli_filter_module.so

sudo install -m 0644 \
    objs/ngx_http_brotli_static_module.so \
    /usr/lib/nginx/modules/ngx_http_brotli_static_module.so


if grep -Eq '^[[:space:]]*include[[:space:]]+/etc/nginx/modules-enabled/\*\.conf;' /etc/nginx/nginx.conf; then
    sudo mkdir -p /etc/nginx/modules-enabled

    sudo tee /etc/nginx/modules-enabled/50-mod-http-brotli.conf >/dev/null <<'EOF'
load_module /usr/lib/nginx/modules/ngx_http_brotli_filter_module.so;
load_module /usr/lib/nginx/modules/ngx_http_brotli_static_module.so;
EOF
else
    if ! grep -q 'ngx_http_brotli_filter_module.so' /etc/nginx/nginx.conf; then
        sudo sed -i '1i\
load_module /usr/lib/nginx/modules/ngx_http_brotli_filter_module.so;\
load_module /usr/lib/nginx/modules/ngx_http_brotli_static_module.so;\
' /etc/nginx/nginx.conf
    fi
fi

sudo tee /etc/nginx/conf.d/10-brotli.conf >/dev/null <<'EOF'
brotli on;
brotli_static on;

brotli_comp_level 5;
brotli_min_length 1024;

brotli_types
    text/plain
    text/css
    text/xml
    application/json
    application/javascript
    application/xml
    application/rss+xml
    application/atom+xml
    application/wasm
    image/svg+xml;
EOF

sudo nginx -t
sudo systemctl restart nginx

nginx -v

sudo nginx -T 2>&1 \
    | grep -E 'load_module.*brotli|brotli(_[a-z]+)?[[:space:]]'


sudo mkdir /etc/pki/nginx
sudo openssl dhparam -out /etc/pki/nginx/dhparam.pem 4096
chown nginx:nginx /etc/pki/nginx/dhparam.pem
# Настраиваем nginx (здесь настройки СТРОГО отдельного домена или поддомена). Если хочется держать в папке, то настраивать nginx нужно по-другому
sudo install -d -m 755 /etc/nginx/snippets

sudo tee /etc/nginx/snippets/vmshpwa-proxy-headers.conf >/dev/null <<'NGINX'
# Клиент не должен подмешивать собственные Forwarded/X-Forwarded-*.
proxy_http_version 1.1;
proxy_set_header Host $host;
proxy_set_header Forwarded "for=\"$remote_addr\";proto=https;host=\"$host\"";

proxy_set_header X-Forwarded-For "";
proxy_set_header X-Forwarded-Host "";
proxy_set_header X-Forwarded-Proto "";
proxy_set_header X-Forwarded-Port "";
proxy_set_header X-Forwarded-Prefix "";
proxy_set_header X-Forwarded-Server "";
proxy_set_header X-Forwarded-Ssl "";
proxy_set_header X-Real-IP "";
proxy_set_header Proxy "";

proxy_connect_timeout 5s;
proxy_request_buffering on;
NGINX


sudo cp -a \
  /web/vmsh_tasks_bot/vmsh_tasks_bot.conf \
  "/web/vmsh_tasks_bot/vmsh_tasks_bot.conf.backup.$(date +%Y%m%d-%H%M%S)"

sudo tee /web/vmsh_tasks_bot/vmsh_tasks_bot.conf >/dev/null <<'NGINX'
# Этот файл подключается внутри блока http через /etc/nginx/conf.d/*.conf.

map $uri $vmshpwa_login_limit_key {
    default "";
    ~^/(student|family|staff)/api/v1/auth/login$ $binary_remote_addr;
}

map $limit_req_status $vmshpwa_retry_after {
    default "";
    REJECTED 60;
}

# Хешированные Vite-assets можно кешировать навсегда.
# Стабильные entry points обязательно перепроверяются.
map $uri $vmshpwa_release_cache_control {
    default "";

    /student/sw.js "no-store";
    /family/sw.js "no-store";

    /student/index.html "no-cache";
    /family/index.html "no-cache";
    /staff/index.html "no-cache";

    /student/manifest.webmanifest "no-cache";
    /family/manifest.webmanifest "no-cache";

    ~^/(student|family|staff)/build-provenance\.json$ "no-cache";
    ~^/(student|family)/icon[^/]*\.(png|svg|webp)$ "no-cache";

    ~^/(student|family|staff)/assets/ "public, max-age=31536000, immutable";
}

map $uri $vmshpwa_service_worker_scope {
    default "";
    /student/sw.js "/student/";
    /family/sw.js "/family/";
}

# Строгие заголовки применяются только к трём новым приложениям.
# Legacy-сайт продолжает работать со своей прежней политикой.
map $uri $vmshpwa_csp {
    default "";
    ~^/(student|family|staff)(/|$) "default-src 'none'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data: blob: @@CSP_MEDIA_ORIGIN@@; media-src 'self' blob: @@CSP_MEDIA_ORIGIN@@; connect-src 'self' wss://vmsh.shashkovs.ru @@CSP_SENTRY_ORIGIN@@; manifest-src 'self'; worker-src 'self' blob:; upgrade-insecure-requests";
}

map $uri $vmshpwa_referrer_policy {
    default "";
    ~^/(student|family|staff)(/|$) "no-referrer";
}

map $uri $vmshpwa_frame_options {
    default "";
    ~^/(student|family|staff)(/|$) "DENY";
}

map $uri $vmshpwa_content_type_options {
    default "";
    ~^/(student|family|staff)(/|$) "nosniff";
}

map $uri $vmshpwa_permissions_policy {
    default "";
    ~^/(student|family|staff)(/|$) "camera=(self), geolocation=(), microphone=(), payment=(), usb=()";
}

limit_req_zone
    $vmshpwa_login_limit_key
    zone=vmshpwa_login_per_ip:10m
    rate=6r/m;

upstream vmsh_legacy_backend {
    server unix:/web/vmsh_tasks_bot/vmsh_tasks_bot.socket fail_timeout=0;
    keepalive 16;
}

upstream vmshpwa_backend {
    server unix:/run/vmshpwa/vmshpwa.sock fail_timeout=0;
    keepalive 16;
}

server {
    listen 80;
    listen [::]:80;

    server_name vmsh.shashkovs.ru;

    return 308 https://vmsh.shashkovs.ru$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;

    server_name vmsh.shashkovs.ru;

    ssl_certificate /etc/letsencrypt/live/vmsh.shashkovs.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vmsh.shashkovs.ru/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/pki/nginx/dhparam.pem;

    root /web/vmsh_tasks_bot/vmshpwa/current;
    index index.html;

    server_tokens off;
    etag on;
    sendfile on;
    tcp_nopush on;

    client_header_timeout 15s;
    client_body_timeout 120s;
    send_timeout 60s;
    keepalive_timeout 65s;

    # Динамический Brotli; если рядом есть file.js.br, сначала используется он.
    brotli on;
    brotli_static on;
    brotli_comp_level 5;
    brotli_min_length 1024;
    brotli_types
        application/javascript
        application/json
        application/manifest+json
        application/wasm
        application/xml
        font/otf
        font/ttf
        image/svg+xml
        text/css
        text/javascript
        text/plain
        text/xml;

    # Fallback для клиентов без Brotli.
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_types
        application/javascript
        application/json
        application/manifest+json
        application/wasm
        application/xml
        font/otf
        font/ttf
        image/svg+xml
        text/css
        text/javascript
        text/plain
        text/xml;

    limit_req
        zone=vmshpwa_login_per_ip
        burst=4
        nodelay;
    limit_req_status 429;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    add_header Content-Security-Policy $vmshpwa_csp always;
    add_header Referrer-Policy $vmshpwa_referrer_policy always;
    add_header X-Frame-Options $vmshpwa_frame_options always;
    add_header X-Content-Type-Options $vmshpwa_content_type_options always;
    add_header Permissions-Policy $vmshpwa_permissions_policy always;

    add_header Retry-After $vmshpwa_retry_after always;
    add_header Cache-Control $vmshpwa_release_cache_control always;
    add_header Service-Worker-Allowed $vmshpwa_service_worker_scope always;

    # ----------------------------------------------------------------------
    # Student, Family и Staff API
    # ----------------------------------------------------------------------

    location ^~ /student/api/ {
        client_max_body_size 64m;

        include /etc/nginx/snippets/vmshpwa-proxy-headers.conf;
        proxy_set_header Connection "";

        proxy_pass http://vmshpwa_backend;
    }

    location ^~ /family/api/ {
        client_max_body_size 64m;

        include /etc/nginx/snippets/vmshpwa-proxy-headers.conf;
        proxy_set_header Connection "";

        proxy_pass http://vmshpwa_backend;
    }

    location ^~ /staff/api/ {
        client_max_body_size 64m;

        include /etc/nginx/snippets/vmshpwa-proxy-headers.conf;
        proxy_set_header Connection "";

        proxy_pass http://vmshpwa_backend;
    }

    location = /student/api {
        return 404;
    }

    location = /family/api {
        return 404;
    }

    location = /staff/api {
        return 404;
    }

    # В production основные media URL ведут прямо в S3.
    # Этот read-only endpoint сохраняется для совместимости.
    location ^~ /pwa-content-assets/ {
        limit_except GET {
            deny all;
        }

        client_max_body_size 1k;

        include /etc/nginx/snippets/vmshpwa-proxy-headers.conf;
        proxy_set_header Connection "";

        proxy_pass http://vmshpwa_backend;
    }

    # ----------------------------------------------------------------------
    # Student, Family и Staff WebSocket
    # ----------------------------------------------------------------------

    location = /student/ws {
        client_max_body_size 64k;

        include /etc/nginx/snippets/vmshpwa-proxy-headers.conf;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 75s;
        proxy_send_timeout 75s;
        proxy_buffering off;

        proxy_pass http://vmshpwa_backend;
    }

    location = /family/ws {
        client_max_body_size 64k;

        include /etc/nginx/snippets/vmshpwa-proxy-headers.conf;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 75s;
        proxy_send_timeout 75s;
        proxy_buffering off;

        proxy_pass http://vmshpwa_backend;
    }

    location = /staff/ws {
        client_max_body_size 64k;

        include /etc/nginx/snippets/vmshpwa-proxy-headers.conf;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 75s;
        proxy_send_timeout 75s;
        proxy_buffering off;

        proxy_pass http://vmshpwa_backend;
    }

    location = /student/ws/ {
        return 404;
    }

    location = /family/ws/ {
        return 404;
    }

    location = /staff/ws/ {
        return 404;
    }

    # ----------------------------------------------------------------------
    # Статические SPA/PWA
    # ----------------------------------------------------------------------

    location = /student {
        return 308 /student/;
    }

    location = /family {
        return 308 /family/;
    }

    location = /staff {
        return 308 /staff/;
    }

    location ^~ /student/ {
        try_files $uri $uri/ /student/index.html;
    }

    location ^~ /family/ {
        try_files $uri $uri/ /family/index.html;
    }

    location ^~ /staff/ {
        try_files $uri $uri/ /staff/index.html;
    }

    # ----------------------------------------------------------------------
    # Старые WebSocket
    # ----------------------------------------------------------------------

    location ^~ /online/ws {
        proxy_http_version 1.1;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;

        # Не сохраняем присланный клиентом X-Forwarded-For.
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Real-IP $remote_addr;

        proxy_read_timeout 1h;
        proxy_send_timeout 1h;
        proxy_buffering off;
        proxy_redirect off;

        proxy_pass http://vmsh_legacy_backend;
    }

    location ^~ /game/ws {
        proxy_http_version 1.1;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;

        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Real-IP $remote_addr;

        proxy_read_timeout 1h;
        proxy_send_timeout 1h;
        proxy_buffering off;
        proxy_redirect off;

        proxy_pass http://vmsh_legacy_backend;
    }

    # ----------------------------------------------------------------------
    # Всё остальное остаётся в существующем приложении
    # ----------------------------------------------------------------------

    location / {
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header Connection "";
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Real-IP $remote_addr;

        proxy_connect_timeout 5s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
        proxy_redirect off;
        proxy_buffering off;

        proxy_pass http://vmsh_legacy_backend;
    }
}
NGINX

sudo sed -i \
  's#@@CSP_MEDIA_ORIGIN@@#https://s3.ru1.storage.beget.cloud#g' \
  /web/vmsh_tasks_bot/vmsh_tasks_bot.conf

sudo sed -i \
  's#@@CSP_SENTRY_ORIGIN@@#https://09d20146c8b808c3760a240956fb3c90@o489435.ingest.us.sentry.io#g' \
  /web/vmsh_tasks_bot/vmsh_tasks_bot.conf

if sudo grep -n '@@' /web/vmsh_tasks_bot/vmsh_tasks_bot.conf; then
    echo "ОШИБКА: в nginx-конфиге остались незаменённые маркеры"
    exit 1
fi



sudo ln -sfn \
  /web/vmsh_tasks_bot/vmsh_tasks_bot.conf \
  /etc/nginx/conf.d/vmsh_tasks_bot.conf

# Проверяем корректность конфига. СУПЕР-ВАЖНО!
sudo nginx -t

# Перезапускаем nginx
sudo systemctl reload nginx.service
sudo systemctl status nginx.service --no-pager

# проверки
curl -sSI https://vmsh.shashkovs.ru/student/
curl -sSI https://vmsh.shashkovs.ru/student/sw.js
curl -sSI -H 'Accept-Encoding: br' https://vmsh.shashkovs.ru/student/
curl -sSI https://vmsh.shashkovs.ru/




sudo systemctl daemon-reload
# Говорим, что нужен автозапуск
sudo systemctl enable gunicorn.vmsh_tasks_bot
# Запускаем
sudo systemctl start gunicorn.vmsh_tasks_bot
# Проверяем
curl --unix-socket /web/vmsh_tasks_bot/vmsh_tasks_bot.socket http

sudo journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago"


/web/vmsh_tasks_bot/vmsh_tasks_bot/.venv/bin




sudo systemctl stop gunicorn.vmsh_tasks_bot
sudo systemctl start gunicorn.vmsh_tasks_bot

cd /web/vmsh_tasks_bot/vmsh_tasks_bot
sudo systemctl stop gunicorn.vmsh_tasks_bot
git pull
chown -R vmsh_tasks_bot:vmsh_tasks_bot /web/vmsh_tasks_bot
# rm -f *.pickle
sudo systemctl start gunicorn.vmsh_tasks_bot
journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago" | tail -n 20



sudo systemctl start gunicorn.vmsh_tasks_bot
sudo systemctl restart gunicorn.vmsh_tasks_bot
journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago" | tail -n 50

# Всё сразу
sudo systemctl restart gunicorn.vmsh_tasks_bot && sudo journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago" -f
sudo journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago" -f
sudo systemctl stop gunicorn.vmsh_tasks_bot
sudo systemctl restart gunicorn.vmsh_tasks_bot

# Просто перезапуск процессов
sudo kill -HUP `cat /web/vmsh_tasks_bot/vmsh_tasks_bot.pid`
# pid = int(open('/web/vmsh_tasks_bot/vmsh_tasks_bot.pid').read().strip())
# os.kill(pid, signal.SIGHUP)

# Подчищаем лог
.headers on
.mode csv
.output message_log_2021-10-01.csv
select * from messages_log where ts < '2021-10-01';
.output stdout
.show
delete from messages_log where ts < '2021-10-01';
vacuum;



sudo -H -u vmsh_tasks_bot git fetch --all


# алиасы в fish в /home/serge/.config/fish/functions
unalias reb
unalias rld
unalias blg
function reb
    cd /web/vmsh_tasks_bot/vmsh_tasks_bot
    sudo chown -R vmsh_tasks_bot:vmsh_tasks_bot /web/vmsh_tasks_bot
    sudo -H -u vmsh_tasks_bot git fetch --all
    sudo systemctl daemon-reload
    sudo systemctl stop gunicorn.vmsh_tasks_bot
    sudo -H -u vmsh_tasks_bot git checkout prod
    sudo -H -u vmsh_tasks_bot git pull
    sudo chown -R vmsh_tasks_bot:vmsh_tasks_bot /web/vmsh_tasks_bot
    sudo systemctl start gunicorn.vmsh_tasks_bot
    sudo journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago" -f
end
funcsave reb
function rld
    sudo systemctl daemon-reload
    sudo systemctl restart gunicorn.vmsh_tasks_bot
end
funcsave rld
function blg
    sudo journalctl -u gunicorn.vmsh_tasks_bot --since "24 hours ago" | tail -n 50
end
funcsave blg
function tbdb
    cd /web/vmsh_tasks_bot/vmsh_tasks_bot/db/
end
funcsave tbdb
function bdb
    sqlite3 /web/vmsh_tasks_bot/vmsh_tasks_bot/db/production.db
end
funcsave bdb

function sbdb
    sudo sqlite3 /web/vmsh_tasks_bot/vmsh_tasks_bot/db/production.db
end
funcsave sbdb


ls -alh /home/serge/.config/fish/functions




# backup destination and user
# timeweb ams
sudo useradd vmsh179botbackup -b /web/ -m -U -s /bin/false
sudo mkdir ~vmsh179botbackup/.ssh
sudo chmod 700 ~vmsh179botbackup/.ssh
sudo touch ~vmsh179botbackup/.ssh/authorized_keys
sudo chmod 600 ~vmsh179botbackup/.ssh/authorized_keys
sudo ssh-keygen -o -a 100 -t ed25519 -f ~vmsh179botbackup/.ssh/id_ed25519_backup -C "vmsh179botbackup@vmsh.shashkovs.ru"
sudo chsh -s /bin/bash vmsh179botbackup
sudo chown vmsh179botbackup:vmsh179botbackup -R ~vmsh179botbackup
# sudo usermod -a -G groupName userName
sudo usermod -a -G web vmsh179botbackup
sudo usermod -a -G vmsh179botbackup serge
sudo cat ~vmsh179botbackup/.ssh/id_ed25519_backup.pub
# ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINh0hgLY67sDP1cwoST7iCatZT+YouDwno9ruliVfsrj vmsh179botbackup@vmsh.shashkovs.ru
# vds
sudo mkdir ~vmsh179botProdBackup/.ssh
sudo chmod 700 ~vmsh179botProdBackup/.ssh
sudo touch ~vmsh179botProdBackup/.ssh/authorized_keys
sudo chmod 600 ~vmsh179botProdBackup/.ssh/authorized_keys
sudo ssh-keygen -o -a 100 -t ed25519 -f ~vmsh179botProdBackup/.ssh/id_ed25519_backup -C "vmsh179botProdBackup@vmsh179botvdsmsk.proj179.ru"
sudo chown vmsh179botProdBackup:vmsh179botProdBackup -R ~vmsh179botProdBackup
sudo cat ~vmsh179botProdBackup/.ssh/id_ed25519_backup.pub
# ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBpGlvBVWPwPQ3LlaW8KzYkKGzufOA7UCNL+4GE3Wms8 vmsh179botProdBackup@vmsh179botvdsmsk.proj179.ru
# timeweb ams
sudo nano /web/vmsh179botbackup/.ssh/authorized_keys
# ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBpGlvBVWPwPQ3LlaW8KzYkKGzufOA7UCNL+4GE3Wms8 vmsh179botProdBackup@vmsh179botvdsmsk.proj179.ru

# test
# vds
ssh -i ~vmsh179botProdBackup/.ssh/id_ed25519_backup -p 22179 vmsh179botbackup@188.245.158.162 "ls -ld /web/vmsh179botbackup && touch /web/vmsh179botbackup/test_file"
ssh -i ~vmsh179botProdBackup/.ssh/id_ed25519_backup -p 22179 vmsh179botbackup@188.245.158.162 "bash -c 'ls -ld /web/vmsh179botbackup && touch /web/vmsh179botbackup/test_file'"
sudo -H -u vmsh179botProdBackup ls /web/vmsh179botProdBackup/vmsh179botProdBackup/db
sudo -H -u vmsh179botProdBackup echo 'yes' > /web/vmsh179botProdBackup/vmsh179botProdBackup/yes.txt
sudo -H -u vmsh179botProdBackup scp -i  ~vmsh179botProdBackup/.ssh/id_ed25519_backup -P 22179 /web/vmsh179botProdBackup/vmsh179botProdBackup/yes.txt vmsh179botbackup@188.245.158.162:/web/vmsh179botbackup
# timeweb ams
sudo ls -alh /web/vmsh179botbackup

# vds
ssh-keygen -o -a 100 -t ed25519 -f ~/.ssh/id_ed25519_backup -C "root@vdsmoscow.proj179.ru"
cat /root/.ssh/id_ed25519_backup.pub
chmod 600 -R /root/.ssh
chmod 700 /root/.ssh
# pq
nano /home/serge/.ssh/authorized_keys
# test vds
cd ~
echo 'yesvds' > yesvds.txt
scp -i /root/.ssh/id_ed25519_backup -P 22179 ~/yesvds.txt serge@188.245.158.162:/web/vmsh_tasks_bot/vmsh_tasks_bot/db


/web/vmsh_tasks_bot/vmsh_tasks_bot/db/backup_to_vds.sh
cat /web/vmsh_tasks_bot/vmsh_tasks_bot/db/backup_to_vds.sh
scp -i /home/serge/.ssh/id_ed25519_backup -P 22179 "/web/vmsh_tasks_bot/vmsh_tasks_bot/db/backups/arch_2023-09-29/arch_2023-09-29T22-49-45.7z" vmsh179botbackup@194.1.237.46:/web/vmsh179botbackup



# backup_to_ams.sh
#!/usr/bin/env bash
nowd=$(date +"%Y-%m-%d")
nowdt=$(date +"%Y-%m-%dT%H-%M-%S")
dump="arch_${nowdt}.dump"
arch="arch_${nowdt}.7z"
dir="backups/arch_${nowd}"
cd /web/vmsh179botProdBackup/vmsh179botProdBackup/db
mkdir -p "${dir}"
sqlite3 production.db .dump > "${dir}/${dump}"
7za a -mx=3 -sdel "${dir}/${arch}" "${dir}/${dump}"
scp -i /root/.ssh/id_ed25519_backup -P 22179 "${dir}/${arch}" serge@188.245.158.162:/web/vmsh_tasks_bot/vmsh_tasks_bot/db



sqlite3 production.db .dump > "$(date +"%Y-%m-%dT%H-%M-%S").dump"


# backup_to_tw_ams.sh
nano /web/vmsh179botProdBackup/vmsh179botProdBackup/db/backup_to_tw_ams.sh
#!/usr/bin/env bash
nowd=$(date +"%Y-%m-%d")
nowdt=$(date +"%Y-%m-%dT%H-%M-%S")
dump="arch_${nowdt}.dump"
arch="arch_${nowdt}.7z"
dir="backups/arch_${nowd}"
cd /web/vmsh179botProdBackup/vmsh179botProdBackup/db
mkdir -p "${dir}"
sqlite3 production.db .dump > "${dir}/${dump}"
7za a -mx=3 -sdel "${dir}/${arch}" "${dir}/${dump}"
scp -i ~vmsh179botProdBackup/.ssh/id_ed25519_backup -P 22179 "${dir}/${arch}" vmsh179botbackup@188.245.158.162:/web/vmsh179botbackup

# Права
chmod +x /web/vmsh179botProdBackup/vmsh179botProdBackup/db/backup_to_tw_ams.sh
chmod g+x /web/vmsh179botProdBackup/vmsh179botProdBackup/db/backup_to_tw_ams.sh
chown vmsh179botProdBackup:vmsh179botProdBackup /web/vmsh179botProdBackup/vmsh179botProdBackup/db/backup_to_tw_ams.sh

# запуск
sudo -H -u vmsh179botProdBackup /web/vmsh179botProdBackup/vmsh179botProdBackup/db/backup_to_tw_ams.sh


# Специальный пользователь для загрузки db
# Создаём restricted bash
sudo ln -s /bin/bash /bin/rbash
sudo useradd vmsh179botvdsdb --create-home --user-group
sudo su - vmsh179botvdsdb
mkdir ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPWnGS2HpbYwOElY8BhzoQrKUX6lh1BC8EtnZIDmbNcU vmsh_tasks_botdb@vmsh.shashkovs.ru
' >> ~/.ssh/authorized_keys
exit
sudo usermod -a -G vmsh_tasks_bot vmsh179botvdsdb
grep -i --color 'vmsh_tasks_bot' /etc/group

# Создаём папку для разрешённых бинарников (yourestricteduser — имя вашего пользователя)
sudo mkdir /home/vmsh179botvdsdb/bin
# Создаём ссылку на команду ls, чтобы её разрешить
sudo ln -s /usr/bin/7za /home/vmsh179botvdsdb/bin/7za
sudo ln -s /usr/local/bin/sqlite3 /home/vmsh179botvdsdb/bin/sqlite3
sudo ln -s /usr/bin/rm /home/vmsh179botvdsdb/bin/rm
# Настройка при логине
sudo nano /home/vmsh179botvdsdb/.bash_profile
# export PATH=$HOME/bin
# Ставим restricted bash при запуске
sudo chsh -s /bin/rbash vmsh179botvdsdb

# Правим права папок по пути
sudo chmod g+w /web/vmsh179botProdBackup/vmsh179botProdBackup/db
sudo chmod g+x /web /web/vmsh179botProdBackup /web/vmsh179botProdBackup/vmsh179botProdBackup

# ssh -F C:\Users\sh57\.ssh\config vmsh179botvdsdb@194.1.237.46 -p 22179 -i "X:\Dropbox\ВМШ 5-7 2023-2024\Py_VMSH_5-7_2023\db\vmsh_tasks_botdb.priv.ppk"
# sudo chsh -s /bin/bash vmsh179botvdsdb








# Восстановление из бекапа
cd /web/vmsh179botbackup
7za x arch_2023-10-06T21-25-56.7z
mv /web/vmsh179botProdBackup/vmsh179botProdBackup/db/production.db /web/vmsh179botProdBackup/vmsh179botProdBackup/db/production_2.db
sqlite3 /web/vmsh179botProdBackup/vmsh179botProdBackup/db/production.db < /web/vmsh179botbackup/backups/arch_2023-10-06/arch_2023-10-06T21-25-56.dump
chown vmsh179botProdBackup:vmsh179botProdBackup /web/vmsh179botProdBackup/vmsh179botProdBackup/db/production.db



cd /web/vmsh179botbackup
sudo 7za x arch_2023-10-23T12-04-25.7z
sudo mv /web/vmsh_tasks_bot/vmsh_tasks_bot/db/production.db /web/vmsh_tasks_bot/vmsh_tasks_bot/db/production_2.db
sudo cp /web/vmsh179botbackup/backups/arch_2023-10-23/arch_2023-10-23T12-04-25.dump /web/vmsh_tasks_bot/vmsh179b
ottw/db/arch_2023-10-23T12-04-25.dump
cd /web/vmsh_tasks_bot/vmsh_tasks_bot/db
sudo chown vmsh_tasks_bot:vmsh_tasks_bot *.dump
sudo -H -u vmsh_tasks_bot sqlite3 production.db < arch_2023-10-23T12-04-25.dump



# crontab -e
0 3 * * * /usr/bin/bash /web/vmsh_tasks_bot/vmsh_tasks_bot/db/backup_to_vds.sh >/dev/null 2>&1
0 13 * * * /usr/bin/bash /web/vmsh_tasks_bot/vmsh_tasks_bot/db/backup_to_vds.sh >/dev/null 2>&1
0 21 * * * /usr/bin/bash /web/vmsh_tasks_bot/vmsh_tasks_bot/db/backup_to_vds.sh >/dev/null 2>&1
0 * * * * sudo -u vmsh_tasks_bot bash -c 'export PROD=true; cd /web/vmsh_tasks_bot/vmsh_tasks_bot && /web/vmsh_tasks_bot/vmsh_tasks_bot/.venv/bin/python -m plugins.calc_complexity >/dev/null'

