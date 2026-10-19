#!/usr/bin/env bash
# Run by an administrator: bounded unit, supplied time range, private output.
set -euo pipefail
if [[ $# != 3 ]]; then
  echo 'Usage: export-journal.sh SINCE UNTIL OUTPUT.jsonl.gz' >&2
  exit 2
fi
umask 077
# noclobber prevents accidentally replacing an existing diagnostic archive.
set -o noclobber
journalctl -u vmshpwa.service --since "$1" --until "$2" --no-pager -o json | gzip > "$3"
