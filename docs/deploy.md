# Что нужно для запуска (кратко)
- В телеграме:
  - Телеграм-бот и токен от него (например, dummy_vmsh_bot);
  - Канал для sos-сообщений (например, dummy_vmsh_sos_channel);
  - Канал для сообщений об ошибках в боте (например, dummy_vmsh_exception_channel);
- В гугле:
  - ключи для google API;
  - гугл-таблица со списком задач, школьников и преподавателей;
- На сервере:
  - доменное имя (можно третьего и выше уровня);
  - sqlite версии ⩾ 3.35.0 (не обязательно системный);
  - python версии ⩾ 3.9 (не обязательно системный);
  - nginx;
  - systemd;
  - SSL-сертификат (например, от certbot'а от let's encrypt);
  - nats-server для межпроцессных взаимодействий. Нужно для корректной работы web-socket'ов.


## Создание бота и каланов в телеграме

### 1. Телеграм-бот и ключ от него (например, dummy_vmsh_bot)
1.  Находим в поиске бота BotFather и «знакомимся» с ним;
2.  Отправляем ему команду `/newbot`, затем вводим имя нашего бота, например, `dummy_vmsh_bot`;
3.  В ответ получим токен бота в духе `1111111111:AAAAAAA_wwwwwwwwwwwwwwwwwwwwwww_UUU`, вписываем его в файл `creds_test/creds_test/vmsh_bot_config_test.json` 
    (за образец можно взять файл `creds_test/vmsh_bot_config_test.json_ex`) в поле "telegram_bot_token";
4.  Создаём публичный канал для sos-сообщений (для вопросов), например, `dummy_vmsh_sos_channel`. Позже его сделаем приватным;
5.  Создаём публичный канал для сообщений о программных ошибках в боте, например, `dummy_vmsh_exception_channel`. Позже его сделаем приватным;
6.  В каждый из каналов `dummy_vmsh_sos_channel` и `dummy_vmsh_exception_channel` добавляем админом нашего бота `dummy_vmsh_bot` 
    и даем ему требуемые разрешения (`Публиковать сообщения`) в соответствующих каналах; 
7.  В файле `creds_test/vmsh_bot_config_test.json` (за образец можно взять файл `creds_test/vmsh_bot_config_test.json_ex`) вписываем 
    в поле "sos_channel" @имя канала (из ссылки-приглашения) `dummy_vmsh_sos_channel`, а в поле "exceptions_channel" - id `dummy_vmsh_exception_channel`;
8.  По желанию можно в боте BotFather поменять нашему боту имя, описание, аватар;
9.  Добавляем боту команды: в боте BotFather вводим команду `/setcommands` и список команд. Начнём с одной: `sos - связаться с живым человеком`; 
10. Позже сделаем каналы приватными, а также добавим описание пользовательских команд в бот;



## Секреты для google API и табличка с настройками (задачами, студентами и учителями)
Для разработки можно взять креды у Сергея Шашкова

### Как получить секреты для google API, если вы хотите создать свои
- идем по адресу https://console.developers.google.com/iam-admin/serviceaccounts/ (при необходимости создаем аккаунт / залогиниваемся)
- выбираем кнопку СОЗДАТЬ ПРОЕКТ (CREATE PROJECT)  (Select a project -> New project)
- в поле название проекта (Project name) вводим `VmshTasksBot` (название может быть любым), Location можно оставить `No organization`, жмём создать (CREATE)
- переходим в проект, слева вверху нажимаем на `три горизонтальных чёрточки -> "API и сервисы" (APIs & Services) -> "Учетные данные" (Credentials)
- ищем сверху по центру кнопку "+ СОЗДАТЬ УЧЕТНЫЕ ДАННЫЕ" (+ CREATE CREDENTIALS), выбираем "Сервисный аккаунт" (Service account)
- вводим название сервисного аккаунта `VmshTasksBotServiceAccount` (название может быть любым), жмём "создать" (Create and continue)
- в поле "Роль" (Role) нажимаем Редактор (Basic -> Editor), следом "Продолжить" (Continue)
- жмём "Готово" (Done)
- в списке сервисных аккаунтов должен появиться созданный сервисный аккаунт;
  Над ним справа-сверху ищем ссылку "Управление сервисными аккаунтами" (Manage service accounts), переходим по ней
- находим в списке наш аккаунт, справа от него нажимаем на вертикальное троеточие ("Действия", Actions), выбираем "Создать ключ" (manage keys).
- выбираем "создать" (add key, Creaty new key), формат — JSON
- получаем файл, кладём этот файл в проект с кодом по адресу `creds_test/vmsh_bot_sheets_creds.json`
- Настраиваем Гугль-таблички (смотри ниже)
- запускаем бота python main.py (в канал `dummy_vmsh_exception_channel` должно прийти сообщение о запуске)
- в телеграме пишем нашему боту `/start`. 
- залогиниваемся в качестве учителя (вводим соответствующий пароль -> посмотреть его можно в БД (`db/test.db`) в отношении `users` 
  (учителя соответствуют type == 2; пароль указан в поле `token`))
- вводим `/ut` (update teachers)
- интерпретатор выкинет полотно с ошибкой, в полотне будет url типа 
  https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=VmshTasksBot, переходим туда
- там будет на выбор ВКЛЮЧИТЬ (ENABLE) и ПОПРОБОВАТЬ ЭТОТ АПИ. Нажимаем ВКЛЮЧИТЬ (ENABLE), ждем несколько минут 
  (изменения подхватываются не сразу, возможно потребуется DISABLE, затем снова ENABLE, чтобы заработало).
- Снова пишем нашему боту `/ut` (необходимо быть залогиненым в качестве учителя - см выше). В ответ (не мгновенно) должны получить `Учителя обновлены`.
- для проверки сос канала (связи с живым человеком) можем написать боту `/sos` -> <любой текст>. 
  Должны получить сообщения с текстом и описанием от кого оно в `dummy_vmsh_sos_channel`.
- готово

### Гугль-табличка с настройками
- Открываем табличку (при необходимости создаем аккаунт / залогиниваемся) 
  https://docs.google.com/spreadsheets/d/1ggev-oRypHxsa8u22gchEbpojHAGzDYYhK8l4IlUnO0/edit?usp=sharing и клонируем её себе (Файл -> создать копию);
- В настройках доступа табличке нужно явно добавить сервисный профайл бота 
  (Настройки доступа (справа вверху) -> вставляем сервисный профайл (e-mail) бота) -> отправить). 
  Сервисный профайл бота можно посмотреть в `client_email` в json-ключе от гугла, он имеет вид `vmshtasksbotserviceaccount@vmshtasksbot-325121.iam.gserviceaccount.com`.
- Ключ из адреса этой новой таблички (вида `1ggev-oRypHxsa8u22gchEbpojHAGzDYYhK8l4IlUnO0`) вписываем в файл `creds_test/vmsh_bot_config_test.json`
  (за образец можно взять файл `creds_test/vmsh_bot_config_test.json_ex`) в поле "google_sheets_key";


## Развёртывание на сервере (проверено на Ubuntu 22)
Далее будут использоваться следующие имена, которые нужно будет заменить на свои.
- vmsh179bot — имя юзера и папочка для проекта;
- vmsh179bot.proj179.ru — домен;
- https://github.com/ShashkovS/vmsh_tasks_bot — репозиторий с кодом;
- /web — папка, в которой будет лежать проект с ботом;

#### Собираем свежий sqlite (не трогаем системный)
``` bash
# См. также https://number1.co.za/upgrading-sqlite-on-centos-to-3-8-3-or-later/
cd /opt
# Качаем код и разархивируем
wget https://www.sqlite.org/2021/sqlite-autoconf-3360000.tar.gz
tar -xzf sqlite-autoconf-3360000
cd /opt/sqlite-autoconf-3360000
# Собираем
./configure
make
sudo make install
```

#### Собираем свежий Python вместе со свежим sqlite (не трогаем системный)
``` bash
cd ~
# Качаем и разархивируем
wget https://www.python.org/ftp/python/3.9.6/Python-3.9.6.tgz
tar xvf Python-3.9.6.tgz
cd ~/Python-3.9*/
# Обязательно ставим LD_RUN_PATH, чтобы подключился свежий sqlite 
LD_RUN_PATH=/usr/local/lib  ./configure --enable-optimizations
# Делаем altinstall, чтобы не задеть системный питон
LD_RUN_PATH=/usr/local/lib sudo make altinstall
```

#### Устанавливаем nginx (можно apache, но настройки будут для nginx'а)
Стандартно для вашей OS

#### Сертификат
Генерим SSL-сертификаты для нашего домена, например, при помощи certbot от let's encrypt
(уже должен быть настроен DNS на этот сервер)
``` bash
certbot --nginx -d vmshtasksbot.proj179.ru
   # /etc/letsencrypt/live/vmshtasksbot.proj179.ru/fullchain.pem
   # Your key file has been saved at:
   # /etc/letsencrypt/live/vmshtasksbot.proj179.ru/privkey.pem
```


#### Новый юзер, папка 
``` bash
# Cоздаём нового пользователя, указываем ему стартовую папку в /web/
useradd vmsh179bot -b /web/ -m -U -s /bin/false
# Делаем каталоги для данных сайта (файлы сайта, логи и временные файлы):
mkdir -p -m 754 /web/vmsh179bot/logs
mkdir -p -m 777 /web/vmsh179bot/tmp
# Чтобы Nginx получил доступ к файлам сайта, добавим пользователя nginx в группу
usermod -a -G vmsh179bot nginx
# Изменяем права доступа на каталог
chmod 755 /web/vmsh179bot
```

#### Клонируем репозиторий, ставим пакеты
``` bash
# Идём в корень проекта
cd /web/vmsh179bot
# Клонируем репу, ветка prod
git clone https://github.com/ShashkovS/vmsh_tasks_bot vmsh179bot
git checkout prod

# Создаём виртуальное окружение, ставим в него pip
cd /web/vmsh179bot
export LD_LIBRARY_PATH=/usr/local/lib
python3.9 -m venv --without-pip vmsh179bot_env
source /web/vmsh179bot/vmsh179bot_env/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python3.9
deactivate
# Теперь устанавливаем зависимости
source /web/vmsh179bot/vmsh179bot_env/bin/activate
pip install -r vmsh179bot/requirements.txt
deactivate
# Делаем юзера и его группу владельцем  всех своих папок
chown -R vmsh179bot:vmsh179bot /web/vmsh179bot/.[^.]*
chown -R vmsh179bot:vmsh179bot /web/vmsh179bot
```

#### Настраиваем запуск сервиса в systemd
Используется связка nginx -> socket -> gunicorn -> app
Создаётся сервис и сокет.

``` bash
# Начинаем с описания сервиса
echo '
[Unit]
Description=Gunicorn instance to serve vmsh179bot
Requires=gunicorn.vmsh179bot.socket
After=network.target

[Service]
PIDFile=/web/vmsh179bot/vmsh179bot.pid
Restart=always
User=vmsh179bot
Group=nginx
RuntimeDirectory=gunicorn
WorkingDirectory=/web/vmsh179bot/vmsh179bot
Environment="PATH=/web/vmsh179bot/vmsh179bot_env/bin"
Environment="PROD=true"
ExecStart=/web/vmsh179bot/vmsh179bot_env/bin/gunicorn  --pid /web/vmsh179bot/vmsh179bot.pid  --workers 1  --bind unix:/web/vmsh179bot/vmsh179bot.socket --worker-class aiohttp.GunicornWebWorker -m 007  main:app
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s TERM $MAINPID
PrivateTmp=true

[Install]
WantedBy=multi-user.target
' > /etc/systemd/system/gunicorn.vmsh179bot.service
```

Теперь создаём настройки socket'а для автоматического старта сервиса, если в socket что-то придёт
``` bash
echo '[Unit]
Description=gunicorn.vmsh179bot.socket

[Socket]
ListenStream=/web/vmsh179bot/vmsh179bot.socket

[Install]
WantedBy=sockets.target
' >  /etc/systemd/system/gunicorn.vmsh179bot.socket
```

``` bash
# Путь к конфигаем
echo 'd /run/gunicorn 0755 vmsh179bot nginx -
' > /etc/tmpfiles.d/gunicorn.vmsh179bot.conf
```


#### Настройка nginx
Настраиваем nginx (здесь настройки СТРОГО отдельного домена или поддомена). Если хочется держать в папке, то настраивать nginx нужно по-другому
``` bash
echo '
    server {
        listen [::]:443 ssl http2; # managed by Certbot
        listen 443 ssl http2; # managed by Certbot
        server_name vmsh179bot.proj179.ru; # managed by Certbot

        ssl_certificate /etc/letsencrypt/live/vmsh179bot.proj179.ru/fullchain.pem; # managed by Certbot
        ssl_certificate_key /etc/letsencrypt/live/vmsh179bot.proj179.ru/privkey.pem; # managed by Certbot
        include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
        ssl_dhparam /etc/ssl/certs/dhparam.pem;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

        location / {
          proxy_set_header Host $http_host;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_redirect off;
          proxy_buffering off;
          proxy_pass http://unix:/web/vmsh179bot/vmsh179bot.socket;     
        }
    }
' > /etc/nginx/conf.d/vmsh179bot.conf
```

Проверяем корректность конфига. СУПЕР-ВАЖНО!
``` bash
nginx -t
```
Перезапускаем nginx
``` bash
sudo systemctl reload nginx.service
```


#### Устанавливаем nats-server для пересылки сообщений между потоками. Нужно при работе в несколько потоков
``` bash
# Устанавливаем golang и nats
cd ~
wget https://dl.google.com/go/go1.19.2.linux-amd64.tar.gz
sudo tar -C /usr/local -xf go1.19.2.linux-amd64.tar.gz
# Проверяем golang
/usr/local/go/bin/go version
# Создаём пользователя для nats
sudo useradd nats -b /web/ -m -U -s /bin/false
sudo chown -R nats:nats /web/nats
sudo usermod -a -G nats serge
sudo chmod -R ug+rwXs,o-rwx /web/nats
# ставим nats
GO111MODULE=on sudo /usr/local/go/bin/go install github.com/nats-io/nats-server/v2@latest
# Смотрим, куда оно установилось
/usr/local/go/bin/go env GOPATH
# Копируем бинарь
sudo cp ~/go/bin/nats-server /web/nats/nats-server
# Создаём конфиг
echo "port: 4222
net: '127.0.0.1'
pid: /web/nats/nats.pid
" > /web/nats/nats.config
# Проверяем запуск
/web/nats/nats-server -c /web/nats/nats.config
# создаём сервис
echo '[Unit]
Description=NATS Server
After=network.target ntp.service

[Service]
PIDFile=/web/nats/nats.pid
Restart=on-failure
PrivateTmp=true
Type=simple
WorkingDirectory=/web/nats
Environment="PATH=/web/vmsh179bot/vmsh179bot_env/bin"
ExecStart=/web/nats/nats-server -c /web/nats/nats.config
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s SIGINT $MAINPID
User=nats
Group=nats

[Install]
WantedBy=multi-user.target
' > /web/nats/nats.service
sudo ln -s /web/nats/nats.service /etc/systemd/system/nats.service
# Снова подновляем права
sudo chown -R nats:nats /web/nats
# запускаем
sudo systemctl daemon-reload
sudo systemctl enable nats
sudo systemctl start nats
# Проверяем логи
sudo systemctl status nats
sudo journalctl -u nats
```


#### Секреты и настройки
Есть окружение `test` и `prod`. Для каждого своя папка с кредами: creds_test и creds_prod.
Соответственно далее `xxxx` — это `test` или `prod`.
Если вы не занимаетесь доработками, то окружение `test` вам не нужно.

- Идёте в папку `/web/vmsh179bot/vmsh179bot/creds_prod`;
- Кладёте в неё секрет от гугла и называете его `vmsh_bot_sheets_creds_prod.json`;
- Создаёте файл `vmsh_bot_config_prod.json` — настройки вмш-телеграм-бота. Должны иметь вид
    ```
    {
      "config_name": "production",
      "telegram_bot_token": "1111111111:AAAAAAA_wwwwwwwwwwwwwwwwwwwwwww_UUU",
      "google_sheets_key": "1ggev-oRypHxsa8u22gchEbpojHAGzDYYhK8l4IlUnO0",
      "webhook_host": "vmsh179bot.proj179.ru",
      "webhook_port": 443,
      "db_filename": "db/production.db",
      "sos_channel": "@dummy_vmsh_sos_channel",
      "exceptions_channel": "@dummy_vmsh_exception_channel",
      "sentry_dsn": ""
    }
    ```
    - sos_channel — имя канала (в котором бот должен быть админом), в который бот будет пересылать сообщения sos. В переменной должна быть либо строка вида "@some_sos_channel", либо число — id канала.
    - exceptions_channel — имя канала (в котором бот должен быть админом), в который бот будет пересылать сообщения о своих запусках, остановках и падениях. В переменной должна быть либо строка вида "@some_channel", либо число — id канала. Чтобы получить id секретного канала, нужно сначала сделать его публичным, указать имя канала текстом, и запустить бота. При запуске бота они пришлёт телеграмовский id канала. После этого канал можно сделать назад приватным.
    - sentry_dsn — это ключ для логов в sentry. Можно не указывать, если нет необходимости в логировании ошибок в sentry. 

#### Тестовый запуск без systemd
``` bash
cd /web/vmsh179bot/vmsh179bot
PROD=true ../vmsh179bot_env/bin/gunicorn  --pid ../vmsh179bot.pid  --workers 1 --bind unix:../vmsh179bot.socket --worker-class aiohttp.GunicornWebWorker -m 007 main:app
```

Если не запустилось, то исправляем проблемы до победного

#### Добавляем в автозапуск и стартуем
``` bash
sudo systemctl enable gunicorn.vmsh179bot.socket
sudo systemctl start gunicorn.vmsh179bot
# Проверяем логи
journalctl -u gunicorn.vmsh179bot --since "5 minutes ago"
```

#### При необходимости обновить код и перезапустить сервис
``` bash
cd /web/vmsh179bot/vmsh179bot
sudo systemctl stop gunicorn.vmsh179bot.socket && sudo systemctl stop gunicorn.vmsh179bot.service
git pull
chown -R vmsh179bot:vmsh179bot /web/vmsh179bot
sudo systemctl start gunicorn.vmsh179bot.service
journalctl -u gunicorn.vmsh179bot --since "5 minutes ago" | tail -n 20
```

#### При необходимости «порыться» в базе
``` bash
sqlite3 /web/vmsh179bot/vmsh179bot/db/production.db
```


### Регистрация команд в botfather
```
sos - связаться с живым человеком
level_novice - перейти в группу начинающих
level_pro - перейти в группу продолжающих
level_expert - перейти в группу профессионалов
online - дистанционные занятия
in_school - очные занятия по понедельникам в школе
```
