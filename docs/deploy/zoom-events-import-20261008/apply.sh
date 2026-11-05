#!/bin/sh
# Run on VMSh as vmsh_tasks_bot; see STATUS.md and the rehearsal report.
set -eu

zoom_import_dir=/web/vmsh_tasks_bot/vmsh_tasks_bot/db/zoom-events-import-20261008
cd "$zoom_import_dir"
sha256sum --check --status checksums.sha256
zoom_import_run=$(date -u +%Y%m%dT%H%M%SZ)
zoom_import_report="$zoom_import_dir/apply-$zoom_import_run.json"

/usr/bin/python3 "$zoom_import_dir/import_zoom_events.py" apply \
    --database /web/vmsh_tasks_bot/vmsh_tasks_bot/db/production_v2.db \
    --source "$zoom_import_dir/main_zoom_events.tsv" \
    --source-sha256 68c0cab8289f9056315fe351e40c051121ec316f6873c0a7e6adc6326f64a20d \
    --backup "$zoom_import_dir/production-before-apply-$zoom_import_run.sqlite3" \
    --report "$zoom_import_report"

chmod 0640 "$zoom_import_report"
