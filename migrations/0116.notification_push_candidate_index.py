"""Bound the repeated push candidate scan; performance STATUS, 8 October 2026."""

from yoyo import step

__depends__ = {"0115.vmsh_public_media_domain"}

# notification_deliveries.list_due_candidates polls every five seconds. Keep
# history out of its due scan; see docs/performance/2026-10-08-fixes.md.
steps = [step(
    "CREATE INDEX notification_events_push_due_idx "
    "ON notification_events (account_id, deliver_after, id, category) "
    "WHERE read_at IS NULL",
    "DROP INDEX notification_events_push_due_idx",
)]
