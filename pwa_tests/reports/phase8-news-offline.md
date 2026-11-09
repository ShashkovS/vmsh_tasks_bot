# Phase 8: offline news proof

Дата: 2026-07-29.

## Граница среза

- Новая таблица IndexedDB не создавалась: лента использует существующий `documents` cache с общим бюджетом 10 МБ.
- Добавлены только два contract-checked типа документов: `news-feed` и `news-post`.
- Ключ содержит runtime/audience на уровне имени Dexie и account owner на уровне записи.
- Успешная страница ленты сохраняет и саму страницу, и detail каждого входящего поста.
- Fallback используется только при сетевом `TypeError`; HTTP denial и malformed contract не заменяются старой копией.

## Проверяемое поведение

- первая страница, cursor-страницы и detail имеют разные ключи;
- после успешного чтения список и публикация открываются без сети;
- другой account ID не получает сохранённые данные;
- Family и Student с одним runtime instance используют разные базы;
- ошибка API/контракта остаётся ошибкой;
- сбой записи кэша не скрывает корректный ответ сервера.

## Результаты

- ESLint и TypeScript (offline, Student, Family): passed.
- Focused offline cache: 8 passed.
- Frontend unit: 73 files, 481 passed.
- Student production PWA build: passed, `injectManifest`, 107 precache entries.
- Family production PWA build: passed, `injectManifest`, 93 precache entries.
- Visual snapshots: не изменялись.

## Следующий срез

Realtime invalidation `news.changed` и Staff hide/restore/local publication workflow; production-browser offline checkpoint добавляется после появления E2E news seed.
