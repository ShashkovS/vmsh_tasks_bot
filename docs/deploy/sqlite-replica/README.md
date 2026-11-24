# Бегущая копия SQLite каждые 10 минут

На независимом сервере `vmsh` (prep, 188.245.158.162) таймер
`vmsh-sqlite-replica.timer` каждые десять минут напрямую забирает с FirstVDS:

| Production | Реплика на vmsh |
|---|---|
| `db/production_v2.db` | `/var/lib/vmsh-sqlite-replica/main.sqlite3` |
| `db/analytics.sqlite3` | `/var/lib/vmsh-sqlite-replica/analytics.sqlite3` |

Ежедневные зашифрованные архивы и их история остаются без изменений. Реплики
хранятся отдельно, доступны только root и не добавлены в состав архивов.
Они не зашифрованы на диске; передача идёт через SSH. Это две последовательные
согласованные копии отдельных БД, а не общая транзакция между ними. Grafana
по-прежнему входит в ежедневный архив.

## Реализация

[replicate.py](replicate.py) запускает `sqlite3_rsync`, затем `PRAGMA quick_check`.
Повторные запуски передают изменившиеся страницы. Systemd сериализует запуски,
дополнительно используется flock. Статус хранит время начала/окончания копии
каждой БД, объём обмена и ошибку. Максимальное время service — девять минут.

На обоих серверах установлена отдельная официальная `sqlite3_rsync` **3.54.1**,
ZIP проверен по SHA3-256 с [официальной страницы](https://sqlite.org/download.html).
Установленные системный SQLite и SQLite приложения **не заменены**. Бинарник и
запись версии находятся под `/web/vmsh_tasks_bot/sqlite-replica/`.
[Документация протокола](https://sqlite.org/rsync.html).

На FirstVDS [origin.py](origin.py) — forced command отдельного root SSH-ключа:
разрешены только роль origin и точные пути этих двух БД, с адреса prep. Shell,
форвардинг и запись в replica через этот ключ запрещены. Скрипт держит shared
lifecycle lock из [runtime_lock.py](../../../db_methods/pwa/runtime_lock.py)
(ADR 0002), не мешая обычным writers и исключая пересечение с maintenance.
Проверки ограничений: [test_sqlite_replica_origin.py](../../../tests/test_sqlite_replica_origin.py).

На prep отдельные ключ и SSH-конфиг лежат в `/etc/vmsh-sqlite-replica/`, host key
FirstVDS взят из уже проверенного cross-backup known_hosts. Каталоги секретов и
данных — 0700, файлы — 0600. Под `/web/vmsh_tasks_bot/sqlite-replica/` доступны
ссылки `config`, `state`, а также исходники, units и запись установки.
В ежедневном архиве сохраняются только маленькие инструменты, units,
установочные сведения и `/etc`; реплики и бинарник туда не входят.

## Проверить или запустить

```bash
ssh vmsh
sudo cat /var/lib/vmsh-sqlite-replica/status.json
sudo systemctl list-timers vmsh-sqlite-replica.timer
sudo systemctl start vmsh-sqlite-replica.service
sudo journalctl -u vmsh-sqlite-replica.service -n 20 --no-pager
```

Каждый запуск включает quick_check. Полная ручная проверка, когда service не
выполняется:

```bash
sudo python3 - <<'PY'
import sqlite3
for name in ('main', 'analytics'):
    with sqlite3.connect(f'file:/var/lib/vmsh-sqlite-replica/{name}.sqlite3?mode=ro', uri=True) as db:
        print(name, db.execute('PRAGMA integrity_check').fetchall())
PY
```

## При восстановлении

Сначала остановить таймер и дождаться завершения service. Получить отдельный
согласованный снимок реплики через SQLite Backup API для восстановления:

```bash
sudo systemctl stop vmsh-sqlite-replica.timer
sudo systemctl stop vmsh-sqlite-replica.service
sudo install -d -m 700 /root/sqlite-restore
sudo python3 - <<'PY'
import os, sqlite3
os.umask(0o077)
for name in ('main', 'analytics'):
    with sqlite3.connect(f'file:/var/lib/vmsh-sqlite-replica/{name}.sqlite3?mode=ro', uri=True) as src:
        with sqlite3.connect(f'/root/sqlite-restore/{name}.sqlite3') as dst:
            src.backup(dst)
            assert dst.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
PY
```

Далее обычная процедура восстановления БД: остановить writers целевого
приложения, установить снимки с правильными владельцами, учесть WAL/SHM и
миграции, проверить и запустить. Саму production-БД этим инструментом не заменять.
После завершения работ включить таймер: `sudo systemctl start vmsh-sqlite-replica.timer`.

Удаления и ошибочные изменения также перейдут в реплику на следующем запуске;
для возврата к прошлой дате остаются ежедневные архивы. При потере production
остановить таймер, чтобы зафиксировать последнюю доступную копию.

## Повторить установку

Взять официальный tools ZIP, проверить SHA3-256, разместить только
`sqlite3_rsync` в `/web/vmsh_tasks_bot/sqlite-replica/` на обеих машинах. Источник
и хеш сохранены в `installation.json`. На prep создать отдельный ed25519 ключ
в `/etc/vmsh-sqlite-replica`, скопировать уже проверенный host key, настроить
[ssh.sh](ssh.sh) и SSH alias `sqlite-origin` (FirstVDS, root, порт 22179).
На источнике добавить публичный ключ с `restrict`, `from` и forced command
`/usr/bin/python3 /web/vmsh_tasks_bot/sqlite-replica/origin.py`.
Разместить скрипты и [units](systemd/) по указанным в них путям, создать
приватный каталог состояния, проверить ручной запуск, затем включить таймер.
Ни служебные ключи, ни копии БД в Git не помещать.
