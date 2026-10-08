# Design-system handoff instructions

- Read every numbered specification, `STATUS.md`, `../../docs/accepted-technical-decisions-2026-07.md` and `../../docs/product-ux-decisions-2026-07.md` before work.
- Work on exactly one phase. The next phase remains blocked until the owner explicitly accepts the current gate and that decision is recorded in `STATUS.md`.
- Art direction alternatives must be executable Storybook compositions using identical content, not static moodboards or generated screenshots.
- Keep the environment quiet, editorial and educational. Mathematics is the focal content; avoid marketing, gamified ranking and decorative spectacle.
- Do not treat current placeholder tokens/pages as approved visual design.
- Reuse the existing React/Tailwind/shadcn/Base UI architecture. Brand marks are repo-native SVG, and interface icons are Lucide.
- Show light/dark, Student/Family/Staff density, mobile/desktop, long Russian mathematical content and error/offline states at each relevant gate.
- Never update visual snapshots before inspecting the diff. Never bypass semantic tokens with raw colors.
- Record evidence, decisions, rejected traits and open questions in `STATUS.md`; do not mark your own work accepted without the owner's decision.

## Traceability And Progress

- Every numbered design document names the concrete components, stories, routes, tests, or assets that implement its accepted requirements.
- Non-trivial implementation code points back to the authoritative numbered design document and accepted product decision.
- Update `STATUS.md` and the affected numbered phase file throughout the work, including partial progress and known gaps; do not wait until final handoff.
