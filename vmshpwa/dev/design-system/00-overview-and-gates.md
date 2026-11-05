# ТЗ дизайн-системы ВМШ 179: обзор и gates

## Назначение

Это задание передаётся визуальной модели по фазам. Требуется не «нарисовать современный интерфейс», а создать спокойную, долговечную образовательную среду, в которой математика заметнее оболочки. Результат должен быть реализован React/TypeScript/Tailwind CSS 4 в существующем Storybook, а затем применён к prototype-страницам трёх приложений.

## Исходный фундамент

- React 19, strict TypeScript, Vite 8;
- Tailwind CSS 4, semantic CSS variables, `@theme inline`;
- shadcn/ui в monorepo-конфигурации, стиль `base-nova`, primitives Base UI;
- Lucide для интерфейсных пиктограмм;
- Student и Family — mobile-first PWA, Staff — постоянно более плотный SPA;
- светлая и тёмная темы, WCAG 2.2 AA, reduced motion;
- исходная locale — русский, обращение только на «вы».

Текущие CSS tokens и страницы — технические placeholders. Их разрешено целенаправленно заменить в рамках принятой фазы. Архитектуру workspace, routing, API contracts и production guards менять нельзя без отдельного согласования.

Обязательные продуктовые inputs для всех фаз: `../../docs/accepted-technical-decisions-2026-07.md`, `../../docs/product-ux-decisions-2026-07.md` и `../development-plan/01-decisions-and-boundaries.md`. Фазовое ТЗ не дублирует все enum values и migration caveats из этих реестров; визуальная модель обязана читать их полностью и не заменять конфигурируемую доменную модель удобным hardcode в story. Первый рабочий corpus — уроки 39–41 сезона 2025–2026 всех трёх уровней; print, быстрый очный ввод, общий Staff→Telegram channel publisher и реальная AI-проверка не должны незаметно попасть в v1 gate. Узкая персональная classroom delivery Student через PWA/Telegram входит в v1 отдельным типизированным flow.

## Последовательность

1. Art direction — 2–3 исполняемых направления.
2. Brand и tokens — выбранное направление превращается в устойчивую систему.
3. UI primitives — визуальная и поведенческая база.
4. Product components — математика и рабочие сценарии.
5. Pages and flows — связные экраны трёх ролей.
6. Storybook and testing — полные matrices, interactions, a11y и visual baseline.
7. Acceptance — общий аудит.

## Approval gate

Следующая фаза не начинается, пока предыдущая не принята владельцем продукта и не записана в `STATUS.md`. До gate разрешены только исправления текущей фазы и исследовательские stories, явно помеченные `Exploration`. Нельзя молча принять один из вариантов или переносить непринятый визуальный язык в production pages.

На каждый gate предоставляются:

- ссылки на Storybook stories и перечень изменённых файлов;
- краткое объяснение решений и trade-offs;
- light/dark, Student/Family/Staff и mobile/desktop примеры, где применимо;
- keyboard и a11y проверка;
- список известных ограничений и вопросов владельцу;
- запись решения в `STATUS.md` после явного принятия.

## Общие запреты

- raw palette utilities (`text-blue-*`, hex/rgb в product JSX) вместо semantic tokens;
- маркетинговые hero-блоки, pricing-card эстетика, gradients/glow/glassmorphism ради эффекта;
- чрезмерные скругления, карточка вокруг каждого абзаца, pills для обычных кнопок;
- декоративные иллюстрации, маскоты, confetti и постоянная анимация;
- цвет как единственный носитель уровня или статуса;
- скрытая нижняя навигация школьника, horizontal scroll основного текста, мелкие touch targets;
- domain/API imports в `packages/ui`;
- обновление visual snapshots без просмотра diff.

## Критерий результата

Система выглядит узнаваемо как «ВМШ 179», но остаётся сдержанной. Длинное условие удобно читать, решение удобно обсуждать, статус отправки невозможно неверно понять, а Staff выдерживает несколько часов непрерывной проверки. Все публичные компоненты представлены состояниями в Storybook и собираются без prototype/MSW в production.
