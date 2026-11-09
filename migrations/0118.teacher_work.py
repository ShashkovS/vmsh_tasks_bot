"""Teacher accounting snapshots and editable evidence; docs/teacher-work.md."""

from yoyo import step

__depends__ = {"0117.frontend_sentry_budget"}

TABLES = {
    "teacher_work_settings": """
      course_id INTEGER PRIMARY KEY REFERENCES courses(id),
      norm_hours REAL NOT NULL DEFAULT 2.3 CHECK(norm_hours BETWEEN 0 AND 24),
      version INTEGER NOT NULL DEFAULT 1 CHECK(version > 0),
      updated_at TEXT NOT NULL, updated_by INTEGER REFERENCES users(id)
    """,
    "teacher_work_aliases": """
      course_id INTEGER NOT NULL REFERENCES courses(id), normalized_name TEXT NOT NULL,
      original_name TEXT NOT NULL, teacher_id INTEGER REFERENCES users(id),
      state TEXT NOT NULL CHECK(state IN ('mapped','ignored','unresolved')),
      version INTEGER NOT NULL CHECK(version > 0),
      updated_at TEXT NOT NULL, updated_by INTEGER NOT NULL REFERENCES users(id),
      PRIMARY KEY(course_id, normalized_name),
      CHECK((state='mapped' AND teacher_id IS NOT NULL) OR
            (state IN ('ignored','unresolved') AND teacher_id IS NULL))
    """,
    "teacher_work_rosters": """
      id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES courses(id),
      event_id INTEGER NOT NULL REFERENCES in_person_events(id),
      raw_text TEXT NOT NULL, source_sha256 TEXT NOT NULL,
      state TEXT NOT NULL CHECK(state IN ('draft','confirmed')),
      rows_json TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
      updated_at TEXT NOT NULL, updated_by INTEGER NOT NULL REFERENCES users(id),
      UNIQUE(course_id, event_id)
    """,
    "teacher_work_shifts": """
      course_id INTEGER NOT NULL REFERENCES courses(id),
      event_id INTEGER NOT NULL REFERENCES in_person_events(id),
      teacher_id INTEGER NOT NULL REFERENCES users(id), rooms_json TEXT NOT NULL,
      starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, norm_hours REAL NOT NULL,
      standard_starts_at TEXT NOT NULL, standard_ends_at TEXT NOT NULL,
      raw_json TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
      updated_at TEXT NOT NULL, updated_by INTEGER NOT NULL REFERENCES users(id),
      PRIMARY KEY(course_id,event_id,teacher_id), CHECK(ends_at > starts_at)
    """,
    "teacher_work_overrides": """
      course_id INTEGER NOT NULL REFERENCES courses(id), cell_key TEXT NOT NULL,
      hours REAL CHECK(hours IS NULL OR hours BETWEEN 0 AND 10000), comment TEXT NOT NULL
        CHECK(length(trim(comment)) BETWEEN 1 AND 2000),
      source_fingerprint TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
      updated_at TEXT NOT NULL, updated_by INTEGER NOT NULL REFERENCES users(id),
      PRIMARY KEY(course_id,cell_key)
    """,
    "teacher_work_mutations": """
      id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES courses(id),
      actor_id INTEGER NOT NULL REFERENCES users(id), request_key TEXT NOT NULL,
      payload_sha256 TEXT NOT NULL, action TEXT NOT NULL, entity_key TEXT NOT NULL,
      before_json TEXT, after_json TEXT NOT NULL, created_at TEXT NOT NULL,
      UNIQUE(actor_id,request_key)
    """,
    "teacher_work_runs": """
      id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES courses(id),
      actor_id INTEGER REFERENCES users(id), request_key TEXT NOT NULL UNIQUE,
      state TEXT NOT NULL CHECK(state IN ('queued','running','completed','failed')),
      started_at TEXT NOT NULL, completed_at TEXT, error_code TEXT,
      source_fingerprint TEXT, snapshot_json TEXT,
      CHECK(snapshot_json IS NULL OR state='completed')
    """,
    "teacher_work_run_requests": """
      actor_id INTEGER NOT NULL REFERENCES users(id), request_key TEXT NOT NULL,
      course_id INTEGER NOT NULL REFERENCES courses(id),
      run_id INTEGER NOT NULL REFERENCES teacher_work_runs(id), created_at TEXT NOT NULL,
      PRIMARY KEY(actor_id,request_key)
    """,
}

steps = [
    step(f"CREATE TABLE {name} ({columns})", f"DROP TABLE {name}")
    for name, columns in TABLES.items()
]
steps.append(
    step(
        "CREATE INDEX teacher_work_latest ON teacher_work_runs(course_id,state,id DESC)",
        "DROP INDEX teacher_work_latest",
    )
)
