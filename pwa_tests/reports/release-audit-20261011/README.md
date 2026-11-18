# Выпуск и аудит — 11 октября 2026

[Состав, оставшиеся ветки и решения](../../../docs/deploy/release-audit-20261011.md).
[Итоговая квитанция](verification.json): код `623d1663` на ВМШ и TLF.
[Общий gate](gate.json) прошёл на идентичном product source digest;
[E2E](e2e.json): content/offline-current, четыре Chromium сценария без retries.

На каждом сайте 25 HTTP checks PASS, compiler 11 и реальная конвертация
полного примера владельца PASS: [ВМШ](vmsh-tikz.json), [TLF](tlf-tikz.json).
SVG 609×235; ВМШ 6008 bytes, TLF 6011 bytes (разные TeX/Cairo versions).
[TLF SVG](tlf-triangle.svg) и белый [preview](tlf-triangle.png) осмотрены:
две фигуры, русские «а)»/«б)», без bitmap glyphs.

![Проверенный результат TLF](tlf-triangle.png)

[Static verifier ВМШ](vmsh-static.json), [проверка TLF](tlf-deployment.json):
public maps отсутствуют; production provenance, canonical GlitchTip и private
upload 402 artifacts на каждом сохранены. На TLF 160 таблиц / 36664 строк
совпали до/после stopped-writer cutover, canonical settings неизменны кроме
release label, NATS PID 1093 сохранён; backup before/after integrity `ok`.
На ВМШ свежий online backup проверен перед push; миграции не менялись.
PWA/legacy Telegram/Zoom/analytics и все cross-backup timers active.

TLF потребовал отдельного [font package correction](tlf-fonts.json):
`cm-super` обеспечивает векторные T2A глифы. До установки bitmap `<image>`
отклонялся штатным SVG sanitizer. Пакеты установлены без обновления остальных
пакетов/перезапуска служб. Tooling/config/maps/installation record доступны
через ссылки `toolchains/cm-super/` под `/web/vmsh_tasks_bot`.

[Мониторинг](grafana-live.json): все 13 Grafana rules enabled и healthy/inactive;
никаких новых test notifications. Исходники готовых cross-backup/Zoom/alerting
operations восстановлены в Git; исходные worktrees/stashes сохранены.
Учёт преподавателей стал готов в `bbbdd1a3` во время аудита, но пока находится
на отдельной ветке: 0118, release gate и up/down/up серверной копии PASS.

Полные локальные логи: `.runtime/release-audit-20261011/` и
`.runtime/vmshpwa/checks/20261011T125603.793534Z/`. Private host build/backup
records: `deploy/releases/tlfprep-20261011-tikz-audit-623d1663d405/` на TLF и
`deploy/runtime/release-audit-20261011/` на ВМШ. Private configs/DB не в Git.
