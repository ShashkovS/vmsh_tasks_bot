# Независимый бэкап S3 на vmsh

`vmsh` (188.245.158.162) каждый час напрямую читает FirstS3:
`https://firsts3.ru`, bucket `vmsh-static-19080553`. Приложение для этого не нужно.
Реализация: [backup.py](backup.py), проверки бюджета:
[tests/test_s3_backup_budget.py](../../../tests/test_s3_backup_budget.py).

Хранится одно актуальное дерево и версии перезаписанных файлов. Удаление объекта
в S3 **не удаляет** сохранённую копию. Полные ежечасные архивы не создаются.
Файлы и имена зашифрованы rclone crypt. Используется существующий пароль архива
FirstVDS из `/etc/vmsh-cross-backup/peer-archive-password`; его независимая копия
нужна для восстановления при потере сервера. Дополнительный crypt salt:
`vmsh-s3-backup-v1` (не секрет). Пароли задаются через stdin `rclone obscure -`.

Ключ S3 с полными правами находится в root-only конфиге: отдельный read-only ключ
провайдер не предоставляет, владелец разрешил использовать существующий.
Инструмент выполняет только чтение S3. Изменения определяются по размеру и
времени изменения объекта на сервере S3; MIME не запрашивается отдельным HEAD
при инвентаризации. Не запускать с этим конфигом команды
удаления или записи в `source:`.

## Где находится

Проверенные systemd units сохранены в [systemd/](systemd/).

На `vmsh`: `/web/vmsh_tasks_bot/s3-backup/` содержит инструменты, units и ссылки
на `/etc/vmsh-s3-backup/rclone.conf`, `/var/lib/vmsh-s3-backup` и rclone.
Конфиг/состояние доступны только root. Таймер `vmsh-s3-backup.timer` запускает
service каждый час в :20 UTC с разбросом до двух минут, включая пропущенный запуск.

Бюджет — **10 000 000 000 байт** всего каталога состояния. Перед копированием
проверяется ожидаемое место с накладными расходами шифрования и запасом для
параллельных передач; дополнительно установлен transfer cap. Это программная
защита, не отдельная файловая квота. На диске оставляется минимум 2 GiB свободного
места. При нехватке места запуск завершается ошибкой, старые объекты и версии
автоматически **не удаляются**. Нужно увеличить бюджет или отдельно решить,
какие версии больше не нужны. Последний результат и ошибка — в `status.json`.

В обычный ежедневный архив входят только конфиг и маленькие исходники/units;
дерево S3, его версии, логи и rclone binary туда **не входят**.

## Проверить / запустить

```bash
ssh vmsh
sudo cat /var/lib/vmsh-s3-backup/status.json
sudo systemctl list-timers vmsh-s3-backup.timer
sudo systemctl start vmsh-s3-backup.service
sudo journalctl -u vmsh-s3-backup.service -n 30 --no-pager
```

Первый запуск и затем раз в 30 дней скачивают исходные объекты заново для полной
побайтовой сверки с расшифрованным бэкапом. Принудительная сверка, когда service
не выполняется:

```bash
sudo python3 /web/vmsh_tasks_bot/s3-backup/tools/backup.py --verify
```

## Восстановить

Команды ниже читают бэкап и пишут только в выбранный локальный каталог.
Не публиковать фотографии учеников и не восстанавливать поверх production без
отдельного решения. Восстановленные файлы хранятся уже без шифрования.

```bash
sudo install -d -m 700 /root/s3-restore
sudo /usr/local/lib/vmsh-s3-backup/rclone \
  --config /etc/vmsh-s3-backup/rclone.conf \
  copy backup:current /root/s3-restore
# Предыдущие версии: ls backup:versions, затем copy нужного подкаталога.
```

Если сервер потерян, нужны сохранённые зашифрованные `objects/` и пароль.
Установить rclone, создать crypt remote `backup` с remote на этот каталог,
`filename_encryption=standard`, `directory_name_encryption=true`, password —
сохранённый пароль, password2 — `vmsh-s3-backup-v1` (оба через `obscure -`).
S3-ключ для расшифровки бэкапа не нужен.

Отключение: `sudo systemctl disable --now vmsh-s3-backup.timer`. Это не удаляет
копии. Не применять `sync`, `purge` или `delete` к дереву бэкапа.

Семантика инструментов: [copy](https://rclone.org/commands/rclone_copy/),
[crypt](https://rclone.org/crypt/), [check](https://rclone.org/commands/rclone_check/).
