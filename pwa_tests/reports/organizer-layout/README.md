# Organizer entry-point layout

[Requirements](../../../vmshpwa/docs/organizer-questions.md). Family home uses a prominent icon action, full-width at mobile sizes. Staff questions share aligned section navigation, active state and count; organizer cards align with the header and filters.

Validation: production build, targeted ESLint, workspace typecheck (Staff route search parameters corrected and Staff typecheck rerun successfully), `e2e/organizer-layout.spec.ts`: **3 passed**, Chromium/WebKit/Firefox on an isolated real backend. Sizes 1280/320/390, dark Staff view, create-question link, pending count and both admin section links. Screenshots include all three engines; dark-theme captures disable transitions to avoid intermediate colours. No API, data or permission changes. Owner authorized commit and push.
