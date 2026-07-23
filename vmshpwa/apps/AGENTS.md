# Application instructions

These rules apply to Student, Family and Staff applications.

- Keep audience boundaries explicit: base path, API path, WebSocket path, session cookie, storage namespace and PWA scope must not leak across apps.
- Route files compose pages and validate URL state. Move genuinely reusable view logic to a suitable package; do not create cross-app relative imports.
- Fetch through audience-relative API endpoints with credentials included and validate payloads through `@vmsh/contracts`.
- Handle loading, empty, error, forbidden and offline states deliberately. Never show protected prototype content as a production authentication fallback.
- Student and Family are mobile-first and touch-safe. Staff remains information-dense and keyboard-efficient while adapting at its supported minimum viewport.
- User-facing copy is Russian and addresses the user as «вы». Avoid sales, urgency and ranking language.
- Keep screen readers, keyboard order, visible focus, 200% zoom and reduced motion working with every UI change.
- Staff is not exempt from the baseline a11y gate. Avoiding a complex DnD dependency means providing simpler buttons/select/move controls, not disabling semantic, keyboard, focus or axe checks.
- Use only semantic tokens and shared primitives. Add app-level tokens only when the concept is truly audience-specific and document them.
