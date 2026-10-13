# Пакетная проверка связей Family–Student

Phase 9 уже содержит отдельный read-only compatibility preview для заполнения
`family_student_links` между существующими аккаунтами. Target v1 workflow не
расширяет этот CSV: Staff выполняет два независимых batch — сначала Student,
затем Family account provisioning.

## Формат CSV

Первая строка содержит ровно четыре колонки в любом порядке:

```csv
family_username,student_public_id,relationship_label,is_primary
family-login,student-public-id,мама,true
```

- `family_username` нормализуется тем же правилом, что Staff account UI;
- `student_public_id` — существующий непрогнозируемый публичный ID школьника;
- `relationship_label` — непустая короткая подпись, например `мама`;
- `is_primary` принимает `true`, `false`, `1` или `0` без учёта регистра.

Одна пара Family account–Student встречается в файле только один раз. Один
Family-аккаунт может ссылаться на нескольких детей, а у ребёнка может быть
несколько семейных аккаунтов.

## Запуск

```bash
PWA_FAMILY_LINK_IMPORT_DATABASE=.runtime/path/copy.sqlite3 \
PWA_FAMILY_LINK_IMPORT_CSV=.runtime/path/family-links.csv \
PWA_FAMILY_LINK_IMPORT_REPORT=.runtime/path/family-links-report.json \
  make pwa-family-link-import-preview
```

SQLite открывается через `mode=ro` и `PRAGMA query_only`. Preview классифицирует
строки как `create`, `restore`, `update` или `unchanged`. Диагностика содержит
только номер строки и стабильный код: Family login и Student public ID остаются
в локальном исходном CSV и не копируются в отчёт.

Отсутствие blockers означает лишь, что compatibility-файл согласован с выбранной
копией БД. Target Family batch принимает `name`, `login`, `password`, список
email через запятую и список login детей. Он создаёт Family account и все links
одним применением после preview. Login/password сохраняются для внешнего v1
email-script; сам Staff письма не отправляет. Один Family account открывает всех
связанных детей в Family PWA.
