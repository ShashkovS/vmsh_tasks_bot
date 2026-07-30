# Phase 11: atomic frontend release rehearsal

Дата: 30 июля 2026 года.

## Результат

Production build трёх приложений успешно собран и упакован в один неизменяемый
release-каталог `.runtime/phase11-rehearsal/releases/c33348e`. Симлинк
`current` атомарно переключён на этот каталог.

| Приложение | Файлов | Размер, байт | SHA-256 дерева |
| --- | ---: | ---: | --- |
| Student | 156 | 3 837 552 | `2214b81eda591db3ea42ce8268448e6942259e831721c9fa979c2a5250d8a26a` |
| Family | 144 | 3 626 138 | `d8c8fbd11059608a095795d213ff5d9d49a86f9916ae0b8a81b6ac77e64d68c8` |
| Staff | 162 | 3 655 524 | `115e76355b9810b6719eb71d9d82f4833dba94bb5a7170915e3b20996db9e56a` |

Перед упаковкой Student и Family проверяются на наличие `index.html`,
`manifest.webmanifest` и `sw.js`; Staff — на `index.html`. Неполная сборка,
повторное использование release ID, небезопасный ID и подмена `current` обычным
файлом или каталогом завершаются ошибкой. Старые release-каталоги скрипт не
удаляет и не изменяет.

## Команды

```shell
make pwa-build

PWA_RELEASE_ID=<revision> \
PWA_RELEASE_REPORT=.runtime/phase11-rehearsal/releases/<revision>-package.json \
make pwa-phase11-release-package

PWA_RELEASE_ID=<revision> \
PWA_RELEASE_REPORT=.runtime/phase11-rehearsal/releases/<revision>-activate.json \
make pwa-phase11-release-activate
```

Возврат выполняется явным выбором ранее проверенного release ID:

```shell
PWA_RELEASE_ID=<previous-revision> \
PWA_RELEASE_REPORT=.runtime/phase11-rehearsal/releases/<revision>-rollback.json \
make pwa-phase11-release-rollback
```

## Проверки

- production build: PASS;
- focused Python suite: `7 passed`;
- синтетическая проверка двух отличающихся полных сборок: `A → B → A`, PASS;
- после возврата `current/student/index.html` содержит байты сборки A;
- Ruff и `git diff --check`: PASS.

## Граница доказательства

Проверены упаковка и атомарное переключение полного frontend-набора на одном
filesystem. Это ещё не полный production deploy/rollback: не переключались
backend revision, migrations, systemd и установленный nginx; не выполнялся
возврат с реального нового production commit на реальный предыдущий commit.
Этот остаток остаётся Phase 11 gate и должен проверяться в изолированном server
rehearsal после утверждения FQDN и точного server layout.
