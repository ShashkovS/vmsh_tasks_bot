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
pnpm self-update next-12


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
cd /web/vmsh_tasks_bot/vmsh_tasks_bot/vmshpwa



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
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACD4ywycYMlAA+X8eAzvpZZOm5Jbl2OYI/pzLvCWYDecOAAAALBjj1f6Y49X
+gAAAAtzc2gtZWQyNTUxOQAAACD4ywycYMlAA+X8eAzvpZZOm5Jbl2OYI/pzLvCWYDecOA
AAAECekFCIbSrDhLR6fpCh3eiixYVjhTLKp22N334a8/PWCPjLDJxgyUAD5fx4DO+llk6b
kluXY5gj+nMu8JZgN5w4AAAALHZtc2gxNzlib3RoemdlcmRiQHZtc2gxNzlib3Roemdlci
5wcm9qMTc5LnJ1AQ==
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

ssh -F C:\Users\sh57\.ssh\config vmsh_tasks_botdb@188.245.158.162 -p 22179 -i "X:\Dropbox\ВМШ 5-7 2024-2025\Py_VMSH_5-7_2024\db\_vmsh_tasks_botdb.priv.ppk"
icacls "X:\Dropbox\ВМШ 5-7 2024-2025\Py_VMSH_5-7_2024\db\_vmsh_tasks_botdb.priv.ppk" /inheritance:r
icacls "X:\Dropbox\ВМШ 5-7 2024-2025\Py_VMSH_5-7_2024\db\_vmsh_tasks_botdb.priv.ppk" /grant:r "$($env:UserName):(R)"







# Проверяем sqlite3
/web/vmsh_tasks_bot/vmsh_tasks_bot_env/bin/python3.12
import sqlite3
sqlite3.version
sqlite3.sqlite_version



# Делаем юзера и его группу владельцем  всех своих папок
sudo chown -R vmsh_tasks_bot:vmsh_tasks_bot /web/vmsh_tasks_bot
# Делаем так, чтобы всё новое лежало в группе





# Настраиваем systemd для поддержания приложения в рабочем состоянии
# Начинаем с описания сервиса
sudo echo '
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
Environment="PATH=/web/vmsh_tasks_bot/vmsh_tasks_bot_env/bin"
Environment="PROD=true"
Environment="LD_RUN_PATH=/usr/local/lib"
Environment="LD_LIBRARY_PATH=/usr/local/lib"
ExecStart=/web/vmsh_tasks_bot/vmsh_tasks_bot_env/bin/gunicorn  --pid /web/vmsh_tasks_bot/vmsh_tasks_bot.pid  --workers 2  --bind unix:/web/vmsh_tasks_bot/vmsh_tasks_bot.socket --worker-class aiohttp.GunicornUVLoopWebWorker -m 007  main:app
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s TERM $MAINPID
PrivateTmp=true

[Install]
WantedBy=multi-user.target
' > /etc/systemd/system/gunicorn.vmsh_tasks_bot.service
sudo ln -s /web/vmsh_tasks_bot/gunicorn.vmsh_tasks_bot.service /etc/systemd/system/gunicorn.vmsh_tasks_bot.service

# Тестовый запуск
cd /web/vmsh_tasks_bot/vmsh_tasks_bot && export PROD=true && /web/vmsh_tasks_bot/vmsh_tasks_bot_env/bin/gunicorn  --pid /web/vmsh_tasks_bot/vmsh_tasks_bot.pid  --workers 2  --bind unix:/web/vmsh_tasks_bot/vmsh_tasks_bot.socket --worker-class aiohttp.GunicornUVLoopWebWorker -m 007  main:app


# # Теперь socket-файл. В нём написано, что если в сокет упадут какие-либо данные, то нужно запустить сервис, если он вдруг не запущен
# sudo echo '[Unit]
# Description=gunicorn.vmsh_tasks_bot.socket

# [Socket]
# ListenStream=/web/vmsh_tasks_bot/vmsh_tasks_bot.socket

# [Install]
# WantedBy=sockets.target
# ' >  /etc/systemd/system/gunicorn.vmsh_tasks_bot.socket

# # Путь к конфигаем
# echo 'd /run/gunicorn 0755 vmsh_tasks_bot nginx -
# ' > /etc/tmpfiles.d/gunicorn.vmsh_tasks_bot.conf


sudo mkdir /etc/pki/nginx
sudo openssl dhparam -out /etc/pki/nginx/dhparam.pem 4096
chown nginx:nginx /etc/pki/nginx/dhparam.pem
# Настраиваем nginx (здесь настройки СТРОГО отдельного домена или поддомена). Если хочется держать в папке, то настраивать nginx нужно по-другому
echo '
    server {
        listen [::]:443 ssl http2; # managed by Certbot
        listen 443 ssl http2; # managed by Certbot
        server_name vmsh.shashkovs.ru; # managed by Certbot

        ssl_certificate /etc/letsencrypt/live/vmsh.shashkovs.ru/fullchain.pem; # managed by Certbot
        ssl_certificate_key /etc/letsencrypt/live/vmsh.shashkovs.ru/privkey.pem; # managed by Certbot
        include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
        ssl_dhparam /etc/pki/nginx/dhparam.pem;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

        location / {
          proxy_set_header Host $http_host;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_redirect off;
          proxy_buffering off;
          proxy_pass http://unix:/web/vmsh_tasks_bot/vmsh_tasks_bot.socket;
        }
        location /online/ws {
          error_log /web/vmsh_tasks_bot/ws.log debug;
          proxy_http_version 1.1;
          proxy_set_header Upgrade $http_upgrade;
          proxy_set_header Connection "Upgrade";
          proxy_set_header Host $http_host;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_redirect off;
          proxy_buffering off;
          proxy_pass http://unix:/web/vmsh_tasks_bot/vmsh_tasks_bot.socket;
        }
        location /game/ws {
          error_log /web/vmsh_tasks_bot/ws.log debug;
          proxy_http_version 1.1;
          proxy_set_header Upgrade $http_upgrade;
          proxy_set_header Connection "Upgrade";
          proxy_set_header Host $http_host;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_redirect off;
          proxy_buffering off;
          proxy_pass http://unix:/web/vmsh_tasks_bot/vmsh_tasks_bot.socket;
        }
    }
' > /web/vmsh_tasks_bot/vmsh_tasks_bot.conf

sudo ln -s /web/vmsh_tasks_bot/vmsh_tasks_bot.conf /etc/nginx/conf.d/vmsh_tasks_bot.conf

# Проверяем корректность конфига. СУПЕР-ВАЖНО!
sudo nginx -t
# Перезапускаем nginx
sudo systemctl reload nginx.service


# Говорим, что нужен автозапуск
sudo systemctl enable gunicorn.vmsh_tasks_bot
# Запускаем
sudo systemctl start gunicorn.vmsh_tasks_bot
# Проверяем
curl --unix-socket /web/vmsh_tasks_bot/vmsh_tasks_bot.socket http

journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago"


/web/vmsh_tasks_bot/vmsh_tasks_bot_env/bin




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
a6Pgm38n362V
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
0 * * * * sudo -u vmsh_tasks_bot bash -c 'export PROD=true; cd /web/vmsh_tasks_bot/vmsh_tasks_bot && /web/vmsh_tasks_bot/vmsh_tasks_bot_env/bin/python -m plugins.calc_complexity >/dev/null'




cd /web/vmsh_tasks_bot
source /web/vmsh_tasks_bot/vmsh_tasks_bot_env/bin/activate.fish
pip install --upgrade numpy



cd /web/vmsh179botProdBackup
source /web/vmsh179botProdBackup/vmsh179botProdBackup_env/bin/activate.fish
pip install --upgrade numpy



sudo -H -u vmsh179botProdBackup  crontab -e
# crontab -e
0 4,12 * * * export LD_RUN_PATH=/usr/local/lib; export LD_LIBRARY_PATH=/usr/local/lib; export PROD=true; cd /web/vmsh179botProdBackup/vmsh179botProdBackup && /web/vmsh179botProdBackup/vmsh179botProdBackup_env/bin/python -m plugins.calc_complexity >/dev/null 2>&1


LD_RUN_PATH=/usr/local/lib &&
Environment="LD_LIBRARY_PATH=/usr/local/lib"
export LD_RUN_PATH=/usr/local/lib; export LD_LIBRARY_PATH=/usr/local/lib; export PROD=true; cd /web/vmsh179botProdBackup/vmsh179botProdBackup && /web/vmsh179botProdBackup/vmsh179botProdBackup_env/bin/python  -m plugins.calc_complexity




vdb
with pre as ( select distinct u.token, r.answer from results r join users u on r.student_id = u.id where u.token not like 'qwerty%' and r.problem_id in (3,9,15) ) select answer, count(*) cnt from pre group by answer order by 2 desc ; with pre as ( select distinct u.token, r.answer from results r join users u on r.student_id = u.id where u.token not like 'qwerty%' and r.problem_id in (2,8,14) ) select answer, count(*) cnt from pre group by answer order by 2 desc ; with pre as ( select distinct u.token, r.answer from results r join users u on r.student_id = u.id where u.token not like 'qwerty%' and r.problem_id in (1,7,13) ) select answer, count(*) cnt from pre group by answer order by 1 ;

vdb
select u.token, (select r2.answer from results r2 where r2.student_id = u.id and r2.ts = (select max(ts) from results r where r.student_id = u.id and r.problem_id in (1,7,13))) q1, (select r2.answer from results r2 where r2.student_id = u.id and r2.ts = (select max(ts) from results r where r.student_id = u.id and r.problem_id in (2,8,14))) q2, (select r2.answer from results r2 where r2.student_id = u.id and r2.ts = (select max(ts) from results r where r.student_id = u.id and r.problem_id in (3,9,15))) q3 from users u where q1 is not null or q2 is not null or q3 is not null ;


with pre as (select distinct lesson, student_id from results where res_type = 4) select lesson, count(*) from pre group by 1 order by 1;


sudo journalctl -u gunicorn.vmsh_tasks_bot --since "2400 days ago" | grep "Кружок по математике для 5-8" >> ~/events_11_10.log



sudo journalctl -u gunicorn.vmsh_tasks_bot --since "24 hours ago" | grep "Кружок по математике для 5-8"



# prod
sudo systemctl restart gunicorn.vmsh_tasks_bot && sudo journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago" -f
# game
sudo systemctl restart gunicorn.vmsh_tasks_bot && sudo journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago" -f


# physics
sudo systemctl restart gunicorn.vmsh_tasks_bot && sudo journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago" -f

# anybody2 mathgame179bot
cd /web/vmsh179bot3/vmsh179bot3 && sudo chown -R vmsh179bot3:vmsh179bot3 /web/vmsh179bot3 && sudo git fetch --all && sudo systemctl daemon-reload && sudo systemctl stop gunicorn.vmsh179bot3.socket && sudo systemctl stop gunicorn.vmsh179bot3.service && sudo git checkout anybody2 && sudo git pull && sudo chown -R vmsh179bot3:vmsh179bot3 /web/vmsh179bot3 && sudo systemctl start gunicorn.vmsh179bot3.socket && sudo systemctl restart gunicorn.vmsh179bot3.service && sudo journalctl -u gunicorn.vmsh179bot3 --since "5 minutes ago" -f
sudo systemctl stop gunicorn.vmsh179bot3.socket && sudo systemctl stop gunicorn.vmsh179bot3.service

# prod4  MSKsq
sudo systemctl restart gunicorn.vmsh_tasks_bot && sudo journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago" -f


sudo systemctl stop gunicorn.vmsh_tasks_bot

sudo systemctl disable gunicorn.vmsh_tasks_bot

#
sudo systemctl restart gunicorn.vmsh_tasks_bot
sudo journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago" -f
#

#
cd /web/vmsh_tasks_bot/vmsh_tasks_bot
#
sudo systemctl restart gunicorn.vmsh_tasks_bot && sudo journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago" -f
#
sudo systemctl stop gunicorn.vmsh_tasks_bot

sudo systemctl stop gunicorn.vmsh179botProdBackup.socket
sudo systemctl stop gunicorn.vmsh179botProdBackup.service
#
sudo systemctl start gunicorn.vmsh179botProdBackup.socket
sudo systemctl start gunicorn.vmsh179botProdBackup.service




sudo systemctl restart gunicorn.vmsh_tasks_bot && sudo journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago" -f


