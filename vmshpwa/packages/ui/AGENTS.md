# Shared UI instructions

`@vmsh/ui` is a domain-neutral shadcn/Base UI foundation.

- Never import app routes, API clients, contracts, student/task/lesson types or domain copy into this package.
- Style exclusively through semantic/component CSS variables. Raw Tailwind palette utilities, arbitrary hex/rgb colors and hidden theme-specific overrides are prohibited.
- Preserve Base UI semantics, controlled/uncontrolled behavior, ref forwarding, focus management and keyboard interactions.
- Every changed public component needs stories for variants and relevant default/hover/focus/disabled/loading/invalid/dark/long-content states.
- Add interaction coverage for behavior such as overlays, menus, form validation, tabs and notifications.
- Icons come from Lucide unless the asset is an approved VMSh brand/product SVG. Icon-only controls require an accessible Russian name at the use site.
- Student touch targets and Staff compact density are token-driven variants, not one-off scaling.
- Do not add a component solely because shadcn offers it; add it for an identified product need.

## Traceability And Progress

- New or materially changed primitives cite the product need/design-system section that requires them and name their stories/tests.
- Design documentation links to the primitive source and story filenames rather than describing an untraceable abstract control.
- Record progress and verification evidence in `dev/design-system/STATUS.md` and the affected numbered specification.
