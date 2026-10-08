# Phase 9: личный прогресс ребёнка в Family

Дата проверки: 2026-07-29.

## Проверяемый результат

- Family home возвращает одну персональную progress-сводку на каждый курс
  связанного ребёнка.
- Сводка использует те же сохранённые результаты, очередь письменной проверки и
  правила active synonym, что Student; второй источник данных не создаётся.
- `courseId` сводки обязан совпадать с курсом конкретного enrollment.
- Family показывает только абсолютные личные числа. Group distribution,
  percentile, позиция и self-marker отсутствуют.
- Связь с ребёнком и enrollment по-прежнему проверяются revalidated Family
  session до чтения результата.

## Автоматические доказательства

```text
Python domain + Family/Student aiohttp/SQLite integration
  6 passed

Family contracts + client
  8 passed

Ruff / ESLint / strict TypeScript
  pass

Family production build
  pass; injectManifest service worker generated

make pwa-e2e-family
  Chromium: pass
  WebKit:   pass
  Firefox:  pass
  total:    3 passed
```

Production/human SQLite, Telegram и Google не использовались. Visual snapshots
не создавались и не обновлялись.
