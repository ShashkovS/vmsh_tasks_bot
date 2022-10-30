# Для взаимодействия между worker'ами используется NATS


Взять бинарь для сервера можно отсюда: 
https://github.com/nats-io/nats-server/releases (файл nats-server-v*.*.*-windows-amd64.zip или соответствующий).

### Сервис в Windows

Дальше его нужно добавить как службу при помощи команды (в админском терминале)
```bash
sc.exe create nats-server binPath= "%NATS_PATH%\nats-server.exe --addr 127.0.0.1 --port 4222 --name vmshtasksbotnats"
```
Дальше его можно запускать/останавливать при помощи
```bash
sc.exe start nats-server
sc.exe stop nats-server
```

### Просто процесс в отдельном терминале

Можно запустить при помощи команды
```bash
# linux
./nats-server --addr 127.0.0.1 --port 4222 --name vmshtasksbotnats
# windows
nats-server.exe --addr 127.0.0.1 --port 4222 --name vmshtasksbotnats
```
