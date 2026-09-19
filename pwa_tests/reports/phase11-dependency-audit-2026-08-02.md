# Phase 11: аудит зафиксированных зависимостей

Дата проверки: 2 августа 2026 года.

## Исполняемый gate

Единая команда `make dependency-audit` проверяет именно закоммиченные lock-файлы:

- `uv audit --frozen` проверяет runtime и dev dependency groups из `uv.lock`
  через OSV;
- `pnpm audit` проверяет production и development graph из
  `vmshpwa/pnpm-lock.yaml` без снижения порога severity;
- ошибки registry/OSV не игнорируются, поэтому отсутствие сети не превращается
  в ложный успешный результат.

Выбор соответствует официальным интерфейсам
[`uv audit`](https://docs.astral.sh/uv/reference/cli/#uv-audit) и
[`pnpm audit`](https://pnpm.io/cli/audit). В gate нет allowlist или ignored
advisories.

## Исправления Python graph

Первый запуск нашёл известные уязвимости в старых версиях `aiohttp`, `click`,
`cryptography`, `httplib2`, `idna`, `pyasn1`, `pygments`, `pytest`, `requests`,
`setuptools` и `urllib3`. Они устранены обновлением lock-файла; в частности:

- `aiohttp 3.13.3` заменён на `3.14.3`;
- совместимый с `aiohttp 3.14` `aiogram 3.30.0` заменил `3.25.0`;
- `pydantic 2.13.4` и `pydantic-core 2.46.4` зафиксированы вместе с новым
  generated Bot API graph;
- неиспользуемые dev-only `importlib`, `paramiko`, `py7zr` и Python-пакет
  `scp` удалены, а не оставлены ради прежнего lock-файла.

`aiogram 3.30` строит новые рекурсивные Rich Message models при импорте. Полная
pytest collection выявила зависимость этого rebuild от порядка уже загруженных
Pydantic namespaces. `pwa_tests/conftest.py` поэтому детерминированно импортирует
aiogram до test modules; production recursion limit не менялся. Обычный import,
полный regression и отдельные исторические Telegram-сценарии прошли.

Остался один adverse status без известной уязвимости: `rsa 4.9.1` помечен
архивным. Он приходит только через legacy Google graph (`google-auth`,
`gspread`, `google-api-python-client`, `oauth2client`) и будет удалён вместе с
согласованным Google cutover. Это не подавленный vulnerability finding.

## Исправления frontend graph

Production-only проверка была чистой, но полный audit справедливо нашёл
`GHSA-mh99-v99m-4gvg` в transitive build/test tooling. В
`vmshpwa/pnpm-workspace.yaml` добавлены минимальные patched overrides для трёх
затронутых диапазонов:

- `brace-expansion 1.x` → `1.1.17`;
- `brace-expansion 2.x` → `2.1.3`;
- `brace-expansion >=4 <5.0.8` → минимальная исправленная `5.0.8`.

Lock-файл пересобран pnpm 11.15.1. Повторный полный audit: **No known
vulnerabilities found**.

## Доказательства

- `make dependency-audit`: Python **0 known vulnerabilities**, frontend **0
  known vulnerabilities**;
- `uv lock --check`: PASS;
- `make python-test`: legacy **121 PASS / 1 intentional skip**, PWA **1547 PASS /
  5 intentional skips**, общий wall time **103.95 s** на восьми workers;
- `make telegram-history-test`: **44 PASS**;
- frontend unit: **110 files / 586 PASS**;
- Storybook interaction/a11y: **50 files / 236 PASS**;
- `make pwa-lint`, `make pwa-typecheck`, `make pwa-build`: PASS;
- `git diff --check`: PASS.

Следующий запуск этого gate обязан происходить после любого изменения
`pyproject.toml`, `uv.lock`, `package.json`, `pnpm-workspace.yaml` или
`pnpm-lock.yaml`, а также непосредственно перед production rollout.
