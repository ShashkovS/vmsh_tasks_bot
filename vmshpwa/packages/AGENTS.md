# Shared package instructions

- A package must have one clear responsibility and no imports from an application.
- Public exports are intentional and typed; avoid reaching into another package's private source path.
- Runtime contracts are Zod-first and have fixtures/tests. Do not replace them with unchecked TypeScript assertions.
- Offline mutations require idempotency keys and preserve client/server timestamps and audit semantics.
- Test utilities never appear in application production dependencies or bundles.
- Keep package dependency direction acyclic: primitives/contracts at the bottom, product composition above them.
- Preserve tree-shaking: avoid module-level browser/network side effects and export optional heavy features separately.
