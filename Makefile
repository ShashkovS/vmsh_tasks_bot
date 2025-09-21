# Makefile to fetch DB files into ./db via scp
# Usage: make dbl

.SHELLFLAGS := -eu -o pipefail -c
SHELL := /bin/bash

.PHONY: db
dbl: db_dir
	@echo "[db] Downloading database from leaders:/web/tlfprepbot/tlfprepbot/db/* ..."
	# Copy all files from the remote db directory into local ./db
	scp -r 'leaders:/web/tlfprepbot/tlfprepbot/db/*' db/
	@echo "[db] Done. Files saved to ./db"

# Ensure the local db directory exists
.PHONY: db_dir
db_dir:
	@mkdir -p db
	@echo "[db] Ensured ./db exists"
