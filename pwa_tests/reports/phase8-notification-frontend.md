# Phase 8B: Student notification frontend proof

Дата: 2026-07-29.

## Граница среза

- `packages/contracts` описывает версионированные события, девять категорий, настройки и read acknowledgement.
- `packages/app-shell` содержит прямой authenticated HTTP client и TanStack Query hooks без отдельного repository/service слоя.
- `packages/product` содержит компактную карточку in-app события и Storybook-сценарий нового и прочитанного состояния.
- Student `/profile/notifications` использует настоящий API для списка событий и push-настроек.
- Непрочитанное событие подтверждается только после трёх непрерывных секунд видимости; уход из viewport или скрытие вкладки сбрасывает таймер.
- Browser Push subscription и Family-экран не входят в этот срез.

## Проверяемое поведение

- contract fixtures проходят runtime Zod validation;
- client строит audience-scoped URL, повторяет запрос один раз после обновления сессии и валидирует ответ;
- страница не помечает карточку прочитанной до истечения трёх секунд;
- прерванная видимость не засчитывается;
- изменение категории сохраняет остальные значения настройки;
- Storybook показывает компактные новое и прочитанное состояния на desktop и mobile.

## Результаты

- ESLint и Stylelint: passed.
- TypeScript typecheck: passed.
- Targeted unit tests: 3 files, 8 passed.
- Full unit tests: 65 files, 457 passed.
- Targeted Storybook browser tests (`product-connectivity--in-app-events`): 1 file, 5 passed.
- Full Storybook browser run: 41 files and 204 tests passed; один существующий сценарий `product-classrooms--plan-dense-two-hundred-students` завершился по timeout и не относится к этому срезу.
- Production build Student, Family and Staff: passed; Student/Family `injectManifest` service workers generated.
- Desktop and 320 px mobile-light stories inspected manually; layout accepted for this increment.
- Browser console: errors absent; only two Storybook-manager deprecation warnings about the future Storybook 11 `PopoverProvider.ariaLabel` requirement.
- Visual snapshots: not updated.
- `git diff --check`: passed before staging.

## Следующий срез

Web Push subscription/delivery and Family notification defaults remain separate increments. News ingest also remains an independent commit.
