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
sudo systemctl restart gunicorn.vmsh_tasks_bot.socket
# Проверяем
curl --unix-socket /web/vmsh_tasks_bot/vmsh_tasks_bot.socket http
journalctl -u vmsh_tasks_bot.service -b
