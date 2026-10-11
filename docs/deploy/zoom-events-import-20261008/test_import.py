"""Isolated operator regressions; no runtime imports or production access."""

import csv
import hashlib
import importlib.util
from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "zoom_import", Path(__file__).resolve().parents[1] / "import_zoom_events.py"
)
IMPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORT)


class ZoomImportTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.database = self.root / "current.sqlite3"
        self.source = self.root / "events.tsv"
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("CREATE TABLE users(id INTEGER PRIMARY KEY)")
            db.execute("CREATE TABLE zoom_queue(zoom_user_name TEXT,enter_ts TEXT,status INT)")
            db.execute("INSERT INTO zoom_queue VALUES('existing','2026-10-08',1)")
            db.execute("CREATE TABLE zoom_events(id INTEGER PRIMARY KEY, event_ts TIMESTAMP,"
                       "event TEXT CHECK(event!='deny'),zoom_user_name TEXT,zoom_user_id INTEGER,"
                       "breakout_room_uuid TEXT,user_id INTEGER REFERENCES users(id))")

    def write_source(self, rows):
        with self.source.open("w", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(IMPORT.COLUMNS)
            writer.writerows(rows)
        return hashlib.sha256(self.source.read_bytes()).hexdigest()

    def row(self, source_id, event="meeting.participant_joined", name="Synthetic", zoom_id="42"):
        return (source_id, "2026-09-14T16:33:55.228000", event, name, zoom_id, "", "")

    def test_nulls_affinity_and_quoted_names_survive(self):
        digest = self.write_source([self.row(43833, name="Synthetic\tname\nline"),
                                    self.row(43834, zoom_id="text-zoom-id")])
        report = IMPORT.run(self.database, self.source, digest, apply=True,
                            backup=self.root / "before.sqlite3")
        with closing(sqlite3.connect(self.database)) as db, db:
            rows = db.execute(IMPORT.SELECT).fetchall()
        self.assertEqual(rows[0][3:], ("Synthetic\tname\nline", 42, None, None))
        self.assertEqual(rows[1][4], "text-zoom-id")
        self.assertEqual(report["backup_integrity"], "ok")

    def test_existing_rows_id_collisions_multiplicity_and_repeat(self):
        with closing(sqlite3.connect(self.database)) as db, db:
            db.executemany(IMPORT.INSERT, [tuple(None if value == "" else value for value in
                                                self.row(1, "existing-event")),
                                           (2, *self.row(2, "same-event")[1:4], 42, None, None)])
        digest = self.write_source([self.row(1, "different-event"), self.row(2, "same-event"),
                                    self.row(3, "same-event"), self.row(4, "another-event")])
        report = IMPORT.run(self.database, self.source, digest, apply=True,
                            backup=self.root / "before.sqlite3")
        self.assertEqual((report["rows_to_insert"], report["already_present"],
                          report["source_ids_reassigned"]), (3, 1, 1))
        repeat = IMPORT.run(self.database, self.source, digest)
        self.assertEqual((repeat["rows_to_insert"], repeat["already_present"]), (0, 4))
        with closing(sqlite3.connect(self.database)) as db, db:
            self.assertEqual(db.execute("SELECT event FROM zoom_events WHERE id=1").fetchone(),
                             ("existing-event",))
            self.assertEqual(db.execute("SELECT count(*) FROM zoom_events WHERE event='same-event'").fetchone(), (2,))

    def test_failed_insert_rolls_back_entire_batch(self):
        digest = self.write_source([self.row(1), self.row(2, "deny")])
        with self.assertRaises(sqlite3.IntegrityError):
            IMPORT.run(self.database, self.source, digest, apply=True,
                       backup=self.root / "before.sqlite3")
        with closing(sqlite3.connect(self.database)) as db, db:
            self.assertEqual(db.execute("SELECT count(*) FROM zoom_events").fetchone(), (0,))

    def test_unresolved_user_id_is_rejected(self):
        row = list(self.row(1))
        row[-1] = "999"
        digest = self.write_source([row])
        with self.assertRaisesRegex(ValueError, "unresolved"):
            IMPORT.run(self.database, self.source, digest)

    def test_changed_source_and_existing_backup_are_rejected(self):
        digest = self.write_source([self.row(1)])
        with self.assertRaisesRegex(ValueError, "SHA256"):
            IMPORT.run(self.database, self.source, "0" * 64)
        backup = self.root / "before.sqlite3"
        backup.write_bytes(b"existing backup")
        with self.assertRaises(FileExistsError):
            IMPORT.run(self.database, self.source, digest, apply=True, backup=backup)
        self.assertEqual(backup.read_bytes(), b"existing backup")


if __name__ == "__main__":
    unittest.main()
