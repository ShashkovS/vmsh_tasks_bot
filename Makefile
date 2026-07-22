# Legacy and vmshpwa development commands.

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

PWA_DIR := vmshpwa
PWA_HUMAN_ENV := VMSH_RUNTIME_PROFILE=pwa-human VMSH_INSTANCE=human VMSH_DB_FILENAME=db/vmshpwa_dev.sqlite3 VMSH_MEDIA_ROOT=.runtime/vmshpwa/human VMSH_NATS_TOPIC_PREFIX=vmshpwa_human VMSH_PWA_PROTOTYPE=true
PWA_AGENT_ENV := VMSH_RUNTIME_PROFILE=pwa-agent VMSH_INSTANCE=agent VMSH_DB_FILENAME=db/vmshpwa_agent.sqlite3 VMSH_MEDIA_ROOT=.runtime/vmshpwa/agent VMSH_NATS_TOPIC_PREFIX=vmshpwa_agent VMSH_PWA_PROTOTYPE=true
PWA_E2E_ENV := VMSH_RUNTIME_PROFILE=pwa-e2e VMSH_INSTANCE=e2e VMSH_DB_FILENAME=db/vmshpwa_e2e.sqlite3 VMSH_MEDIA_ROOT=.runtime/vmshpwa/e2e VMSH_NATS_TOPIC_PREFIX=vmshpwa_e2e VMSH_PWA_PROTOTYPE=true

.PHONY: pwa-dev pwa-api pwa-student pwa-family pwa-staff pwa-storybook
pwa-dev:
	$(MAKE) -j5 pwa-api pwa-student pwa-family pwa-staff pwa-storybook

pwa-api:
	$(PWA_HUMAN_ENV) VMSH_API_PORT=8180 uv run python main.py

pwa-student:
	cd $(PWA_DIR) && CI=true VITE_PORT=5173 VMSH_API_ORIGIN=http://127.0.0.1:8180 pnpm --filter @vmsh/student dev

pwa-family:
	cd $(PWA_DIR) && CI=true VITE_PORT=5174 VMSH_API_ORIGIN=http://127.0.0.1:8180 pnpm --filter @vmsh/family dev

pwa-staff:
	cd $(PWA_DIR) && CI=true VITE_PORT=5175 VMSH_API_ORIGIN=http://127.0.0.1:8180 pnpm --filter @vmsh/staff dev

pwa-storybook:
	cd $(PWA_DIR) && CI=true STORYBOOK_PORT=6006 pnpm storybook

.PHONY: pwa-agent-dev pwa-agent-api pwa-agent-student pwa-agent-family pwa-agent-staff pwa-agent-storybook
pwa-agent-dev:
	$(MAKE) -j5 pwa-agent-api pwa-agent-student pwa-agent-family pwa-agent-staff pwa-agent-storybook

pwa-agent-api:
	$(PWA_AGENT_ENV) VMSH_API_PORT=8280 uv run python main.py

pwa-agent-student:
	cd $(PWA_DIR) && CI=true VITE_PORT=5273 VMSH_API_ORIGIN=http://127.0.0.1:8280 pnpm --filter @vmsh/student dev

pwa-agent-family:
	cd $(PWA_DIR) && CI=true VITE_PORT=5274 VMSH_API_ORIGIN=http://127.0.0.1:8280 pnpm --filter @vmsh/family dev

pwa-agent-staff:
	cd $(PWA_DIR) && CI=true VITE_PORT=5275 VMSH_API_ORIGIN=http://127.0.0.1:8280 pnpm --filter @vmsh/staff dev

pwa-agent-storybook:
	cd $(PWA_DIR) && CI=true STORYBOOK_PORT=6106 pnpm storybook

.PHONY: pwa-seed pwa-agent-seed
pwa-seed:
	$(PWA_HUMAN_ENV) uv run python -m vmshpwa.scripts.seed_runtime

pwa-agent-seed:
	$(PWA_AGENT_ENV) uv run python -m vmshpwa.scripts.seed_runtime

.PHONY: pwa-format pwa-lint pwa-typecheck pwa-test pwa-storybook-test pwa-build pwa-e2e pwa-visual pwa-visual-update telegram-history-test
pwa-format:
	cd $(PWA_DIR) && CI=true pnpm format

pwa-lint:
	cd $(PWA_DIR) && CI=true pnpm lint

pwa-typecheck:
	cd $(PWA_DIR) && CI=true pnpm typecheck

pwa-test:
	cd $(PWA_DIR) && CI=true pnpm test
	$(PWA_E2E_ENV) uv run pytest -q -n0 pwa_tests

pwa-storybook-test:
	cd $(PWA_DIR) && CI=true pnpm storybook:test

pwa-build:
	cd $(PWA_DIR) && CI=true pnpm build

pwa-e2e:
	cd $(PWA_DIR) && CI=true pnpm e2e

pwa-visual:
	cd $(PWA_DIR) && CI=true pnpm e2e:visual

pwa-visual-update:
	cd $(PWA_DIR) && CI=true pnpm e2e:visual:update

telegram-history-test:
	uv run pytest -q tests/test_handler_flows.py tests/test_admin_weekly_ops.py
