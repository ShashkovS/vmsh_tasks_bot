from datetime import UTC, datetime

from db_methods.pwa.product_analytics import (
    ProductAnalyticsConnectionFactory,
    prune_expired_events,
    school_year_cutoff,
)


def test_analytics_store_uses_wal_and_prunes_at_moscow_school_year_boundary(tmp_path):
    factory = ProductAnalyticsConnectionFactory(tmp_path / "analytics.sqlite3")
    assert factory.run_read(
        lambda connection: connection.execute("PRAGMA journal_mode").fetchone()
    )["journal_mode"].casefold() == "wal"
    factory.run_write(
        lambda connection: connection.executemany(
            "INSERT INTO product_events (occurred_at, audience, account_public_id, session_public_id, event_type, route_id, entity_type, entity_public_id, viewport_width, viewport_height, device_pixel_ratio, pointer_type, display_mode) VALUES (?, 'student', 'u-2', 'a' * 32, 'page.view', '/', NULL, NULL, 800, 600, 2, 'fine', 'browser')",
            [("2026-08-09T20:59:59+00:00",), ("2026-08-10T21:00:00+00:00",)],
        )
    )
    removed = factory.run_write(
        lambda connection: prune_expired_events(
            connection, now=datetime(2026, 8, 20, tzinfo=UTC)
        )
    )
    assert removed == 1
    assert factory.run_read(
        lambda connection: connection.execute("SELECT COUNT(*) AS count FROM product_events").fetchone()
    )["count"] == 1


def test_school_year_cutoff_uses_tenth_of_august_in_moscow():
    assert school_year_cutoff(datetime(2026, 8, 9, 20, tzinfo=UTC)).isoformat() == "2025-08-09T21:00:00+00:00"
    assert school_year_cutoff(datetime(2026, 8, 10, 21, tzinfo=UTC)).isoformat() == "2026-08-09T21:00:00+00:00"
