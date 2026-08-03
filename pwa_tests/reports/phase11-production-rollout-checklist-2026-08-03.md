# Phase 11: production rollout checklist — 3 августа 2026

## Результат

Создан единый операторский
[`production-rollout-checklist.md`](../../vmshpwa/docs/production-rollout-checklist.md),
который связывает существующие Phase-11 команды в строгий порядок:

1. идентификация revision/schema/rollback target;
2. локальные quality gates, migration и restore rehearsal;
3. frozen build и verified static release;
4. остановка всех SQLite writers и отдельная migration;
5. systemd/nginx checks, activation и public HTTP smoke;
6. authenticated/device/observability checks;
7. явный rollback при нарушении условий.

В документе отделены автоматически доказуемые проверки от server, physical
device и owner gates. `NOT RUN` нельзя выдавать за `PASS`; launcher failure не
считается выполненным browser test. Секреты, персональные данные и полные media
URL запрещено переносить в evidence bundle.

## Проверка

- Все упомянутые `make` targets существуют в корневом `Makefile`.
- Локальные Markdown-ссылки из нового документа, `deployment.md` и Phase 11
  разрешаются в существующие файлы.
- `git diff --check` — PASS.

Это software/documentation proof. Production-копия чек-листа пока не заполнена;
реальный FQDN, service user, backups, migrations, device smoke, alerts и owner
acceptance остаются открытыми Phase-11 gates.
