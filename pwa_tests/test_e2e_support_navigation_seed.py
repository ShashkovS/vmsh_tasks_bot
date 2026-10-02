"""Additional course is isolated test wiring, never production auth wiring."""

import sqlite3

from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.auth import PwaAuthRepository
from pwa_tests.test_e2e_statistics_seed import _owners
from vmshpwa.scripts.seed_e2e_support_navigation import _seed


async def test_support_course_seed_is_idempotent_and_accessible_to_student(tmp_path):
    path = tmp_path / "support.sqlite3"
    apply_schema_migrations(path)
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        _owners(connection)
        assert _seed(connection) == 1
        assert _seed(connection) == 0
        assert (
            connection.execute(
                "SELECT count(*) FROM course_enrollments e JOIN courses c ON c.id=e.course_id "
                "JOIN groups g ON g.group_id=e.active_group_id AND g.course_id=c.id "
                "WHERE e.student_user_id=101 AND c.code='support-navigation' "
                "AND e.status='active' AND c.status='active' AND g.status='active'"
            ).fetchone()[0]
            == 1
        )
    enrollments = await PwaAuthRepository(
        PwaConnectionFactory(path)
    ).list_course_enrollments(
        student_user_id=101,
    )
    assert enrollments[0].course_code == "support-navigation"
    assert (
        enrollments[0].active_group_public_id
        == enrollments[0].allowed_groups[0].group_public_id
    )
