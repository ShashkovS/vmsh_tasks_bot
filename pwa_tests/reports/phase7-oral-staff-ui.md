# Phase 7: Staff-интерфейс устного приёма

Дата проверки: 2026-07-29.

## Что работает

- `/staff/oral?groupLesson=…&tab=results` доступен teacher и admin с правом
  `oral.manage`.
- Форма загружает реальный roster выбранного группового занятия, позволяет выбрать
  школьника, поставить плюс/минус по нескольким задачам и выбрать необязательную
  внутреннюю реакцию.
- Незавершённый раунд сохраняется в `localStorage` отдельно для аккаунта и занятия.
- После успешной записи черновик очищается и создаётся новый idempotency key.
- Admin отдельно открывает `tab=windows`; преподавателю эта вкладка не показывается.
- Product-компонент зафиксирован в Storybook как
  `Product/Oral administration--Compact round` и имеет interaction-проверку.

## Проверки

```text
tsc --noEmit:
  packages/contracts
  packages/app-shell
  packages/product
  apps/staff
pass

eslint (только файлы среза)
pass

vitest unit:
  packages/contracts/src/oral-results.test.ts
  packages/app-shell/src/staff-oral-result-client.test.ts
3 passed

vitest Storybook browser:
  packages/product/src/oral-result-form.stories.tsx
2 passed

vite build (apps/staff)
pass
```

Snapshots не обновлялись.

## Реализация

- contract: `vmshpwa/packages/contracts/src/oral-results.ts`;
- HTTP client: `vmshpwa/packages/app-shell/src/staff-oral-result-client.ts`;
- product component: `vmshpwa/packages/product/src/oral-result-form.tsx`;
- production page: `vmshpwa/apps/staff/src/staff-oral-results-page.tsx`;
- route: `vmshpwa/apps/staff/src/routes/oral.tsx`.
