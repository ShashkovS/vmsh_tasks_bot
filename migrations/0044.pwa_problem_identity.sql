-- depends: 0043.pwa_lesson_window_audit

-- Phase 3 compact browser identity for legacy-backed problems. Authoritative
-- contract: vmshpwa/dev/development-plan/07-phase-3-student-reading.md.
-- The integer primary key remains the internal Telegram/domain FK. Existing
-- and future legacy inserts expose a virtual `p-<id>` without requiring the
-- bot or old import scripts to know about the PWA contract.
alter table problems add column public_id text
    generated always as ('p-' || id) virtual;
