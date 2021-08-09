# Заменить:
# vmsh_tasks_bot (например, vmsh)
# proj179.ru (например, shashkovs.ru или proj179.ru)
# vmsh_tasks_bot (имя проекта, его папка, юзер, адрес и т.п.)
# https://github.com/ShashkovS/vmsh_tasks_bot (репозиторий)

# Настраиваем dns для нового поддомена
# ...


# Настраиваем ssl для нового поддомена
certbot --nginx -d vmshtasksbot.proj179.ru
   # /etc/letsencrypt/live/vmshtasksbot.proj179.ru/fullchain.pem
   # Your key file has been saved at:
   # /etc/letsencrypt/live/vmshtasksbot.proj179.ru/privkey.pem

# Содержимое каждого сайта будет находиться в собственном каталоге, поэтому создаём нового пользователя без возможности логиниться
useradd vmsh_tasks_bot -b /web/ -m -U -s /bin/false

# Делаем каталоги для данных сайта (файлы сайта, логи и временные файлы):
mkdir -p -m 754 /web/vmsh_tasks_bot/logs
mkdir -p -m 777 /web/vmsh_tasks_bot/tmp

# Чтобы Nginx получил доступ к файлам сайта, добавим пользователя nginx в группу
usermod -a -G vmsh_tasks_bot nginx


# Клонируем репу
cd /web/vmsh_tasks_bot
git clone https://github.com/ShashkovS/vmsh_tasks_bot

# готовим виртуальное окружение
cd /web/vmsh_tasks_bot
python3.8 -m venv --without-pip vmsh_tasks_bot_env
source /web/vmsh_tasks_bot/vmsh_tasks_bot_env/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python3
deactivate
# Ставим в него пакеты
source /web/vmsh_tasks_bot/vmsh_tasks_bot_env/bin/activate
cd /web/vmsh_tasks_bot/vmsh_tasks_bot
# Ставим пакеты
pip install -r requirements.txt
deactivate

# Делаем юзера и его группу владельцем  всех своих папок
chown -R vmsh_tasks_bot:vmsh_tasks_bot /web/vmsh_tasks_bot/.[^.]*
chown -R vmsh_tasks_bot:vmsh_tasks_bot /web/vmsh_tasks_bot
chmod -R g+rws /web/vmsh_tasks_bot/.[^.]*
chmod -R g+rws /web/vmsh_tasks_bot
# Делаем так, чтобы всё новое лежало в группе
setfacl -R -m g::rwx $(realpath .)


# Настраиваем systemd для поддержания приложения в рабочем состоянии
# Начинаем с описания сервиса
echo '
[Unit]
Description=Gunicorn instance to serve vmsh_tasks_bot
Requires=gunicorn.vmsh_tasks_bot.socket
After=network.target

[Service]
PIDFile=/web/vmsh_tasks_bot/vmsh_tasks_bot.pid
Restart=on-failure
User=vmsh_tasks_bot
Group=nginx
RuntimeDirectory=gunicorn
WorkingDirectory=/web/vmsh_tasks_bot/vmsh_tasks_bot
Environment="PATH=/web/vmsh_tasks_bot/vmsh_tasks_bot_env/bin"
ExecStart=/web/vmsh_tasks_bot/vmsh_tasks_bot_env/bin/gunicorn  --pid /web/vmsh_tasks_bot/vmsh_tasks_bot.pid  --workers 1  --bind unix:/web/vmsh_tasks_bot/vmsh_tasks_bot.socket --worker-class aiohttp.GunicornWebWorker -m 007  main:app
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s TERM $MAINPID
PrivateTmp=true

[Install]
WantedBy=multi-user.target
' > /etc/systemd/system/gunicorn.vmsh_tasks_bot.service

# Теперь socket-файл. В нём написано, что если в сокет упадут какие-либо данные, то нужно запустить сервис, если он вдруг не запущен
echo '[Unit]
Description=gunicorn.vmsh_tasks_bot.socket

[Socket]
ListenStream=/web/vmsh_tasks_bot/vmsh_tasks_bot.socket

[Install]
WantedBy=sockets.target
' >  /etc/systemd/system/gunicorn.vmsh_tasks_bot.socket

# Путь к конфигаем
echo 'd /run/gunicorn 0755 vmsh_tasks_bot nginx -
' > /etc/tmpfiles.d/gunicorn.vmsh_tasks_bot.conf


# Говорим, что нужен автозапуск
sudo systemctl enable gunicorn.vmsh_tasks_bot.socket
# Запускаем
sudo systemctl stop gunicorn.vmsh_tasks_bot
# Проверяем
curl --unix-socket /web/vmsh_tasks_bot/vmsh_tasks_bot.socket http

journalctl -u gunicorn.vmsh_tasks_bot --since "1 hour ago"

# Настраиваем nginx (здесь настройки СТРОГО отдельного домена или поддомена). Если хочется держать в папке, то настраивать nginx нужно по-другому
echo '
    server {
        listen [::]:443 ssl http2; # managed by Certbot
        listen 443 ssl http2; # managed by Certbot
        server_name vmshtasksbot.proj179.ru; # managed by Certbot

        ssl_certificate /etc/letsencrypt/live/vmshtasksbot.proj179.ru/fullchain.pem; # managed by Certbot
        ssl_certificate_key /etc/letsencrypt/live/vmshtasksbot.proj179.ru/privkey.pem; # managed by Certbot
        include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
        ssl_dhparam /etc/ssl/certs/dhparam.pem;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

        location / {
          proxy_set_header Host $http_host;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_redirect off;
          proxy_buffering off;
          proxy_pass http://unix:/web/vmsh_tasks_bot/vmsh_tasks_bot.socket;
        }
    }
' > /etc/nginx/conf.d/vmshtasksbot.conf

# Проверяем корректность конфига. СУПЕР-ВАЖНО!
nginx -t
# Перезапускаем nginx
systemctl reload nginx.service


# Полный перезапуск всего
# Стопим сервис
sudo systemctl stop gunicorn.vmsh_tasks_bot.socket && sudo systemctl stop gunicorn.vmsh_tasks_bot.service
# Освежаем
cd /web/vmsh_tasks_bot/vmsh_tasks_bot
git pull
chown -R vmsh_tasks_bot:vmsh_tasks_bot /web/vmsh_tasks_bot
# Запускаем
sudo systemctl start gunicorn.vmsh_tasks_bot.socket && sudo systemctl restart gunicorn.vmsh_tasks_bot.service
# Проверяем
journalctl -u gunicorn.vmsh_tasks_bot --since "5 minutes ago" | tail -n 50
