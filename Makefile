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
PWA_UV_ENV := UV_CACHE_DIR=.runtime/uv-cache
PWA_HUMAN_ENV := VMSH_RUNTIME_PROFILE=pwa-human VMSH_INSTANCE=human VMSH_DB_FILENAME=db/vmshpwa_dev.sqlite3 VMSH_MEDIA_ROOT=.runtime/vmshpwa/human VMSH_NATS_SERVER=nats://127.0.0.1:4222 VMSH_NATS_TOPIC_PREFIX=vmshpwa_human VMSH_PWA_PROTOTYPE=true
PWA_AGENT_ENV := VMSH_RUNTIME_PROFILE=pwa-agent VMSH_INSTANCE=agent VMSH_DB_FILENAME=db/vmshpwa_agent.sqlite3 VMSH_MEDIA_ROOT=.runtime/vmshpwa/agent VMSH_NATS_SERVER=nats://127.0.0.1:4222 VMSH_NATS_TOPIC_PREFIX=vmshpwa_agent VMSH_PWA_PROTOTYPE=true
PWA_E2E_ENV := VMSH_RUNTIME_PROFILE=pwa-e2e VMSH_INSTANCE=e2e VMSH_DB_FILENAME=db/vmshpwa_e2e.sqlite3 VMSH_MEDIA_ROOT=.runtime/vmshpwa/e2e VMSH_NATS_SERVER= VMSH_NATS_TOPIC_PREFIX=vmshpwa_e2e VMSH_PWA_PROTOTYPE=true

.PHONY: pwa-dev pwa-api pwa-student pwa-family pwa-staff pwa-storybook
pwa-dev:
	$(MAKE) -j5 pwa-api pwa-student pwa-family pwa-staff pwa-storybook

pwa-api:
	$(PWA_UV_ENV) $(PWA_HUMAN_ENV) VMSH_API_PORT=8180 uv run python main.py

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
	$(PWA_UV_ENV) $(PWA_AGENT_ENV) VMSH_API_PORT=8280 uv run python main.py

pwa-agent-student:
	cd $(PWA_DIR) && CI=true VITE_PORT=5273 VMSH_API_ORIGIN=http://127.0.0.1:8280 pnpm --filter @vmsh/student dev

pwa-agent-family:
	cd $(PWA_DIR) && CI=true VITE_PORT=5274 VMSH_API_ORIGIN=http://127.0.0.1:8280 pnpm --filter @vmsh/family dev

pwa-agent-staff:
	cd $(PWA_DIR) && CI=true VITE_PORT=5275 VMSH_API_ORIGIN=http://127.0.0.1:8280 pnpm --filter @vmsh/staff dev

pwa-agent-storybook:
	cd $(PWA_DIR) && CI=true STORYBOOK_PORT=6106 pnpm storybook

.PHONY: pwa-migrate pwa-agent-migrate pwa-e2e-migrate pwa-seed pwa-agent-seed pwa-toolchain-check pwa-agent-toolchain-check pwa-toolchain-smoke pwa-agent-toolchain-smoke
pwa-migrate:
	$(PWA_UV_ENV) $(PWA_HUMAN_ENV) uv run python -m vmshpwa.scripts.migrate_runtime

pwa-agent-migrate:
	$(PWA_UV_ENV) $(PWA_AGENT_ENV) uv run python -m vmshpwa.scripts.migrate_runtime

pwa-e2e-migrate:
	$(PWA_UV_ENV) $(PWA_E2E_ENV) uv run python -m vmshpwa.scripts.migrate_runtime

pwa-seed:
	$(PWA_UV_ENV) $(PWA_HUMAN_ENV) uv run python -m vmshpwa.scripts.seed_runtime

pwa-agent-seed:
	$(PWA_UV_ENV) $(PWA_AGENT_ENV) uv run python -m vmshpwa.scripts.seed_runtime

pwa-toolchain-check:
	$(PWA_UV_ENV) $(PWA_HUMAN_ENV) uv run python -m vmshpwa.scripts.toolchain_preflight

pwa-agent-toolchain-check:
	$(PWA_UV_ENV) $(PWA_AGENT_ENV) uv run python -m vmshpwa.scripts.toolchain_preflight

pwa-toolchain-smoke:
	$(PWA_UV_ENV) $(PWA_HUMAN_ENV) uv run python -m vmshpwa.scripts.toolchain_smoke

pwa-agent-toolchain-smoke:
	$(PWA_UV_ENV) $(PWA_AGENT_ENV) uv run python -m vmshpwa.scripts.toolchain_smoke

.PHONY: pwa-golden-check pwa-golden-update
pwa-golden-check:
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.golden_corpus check

pwa-golden-update:
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.golden_corpus write

.PHONY: pwa-content-story-corpus-check pwa-content-story-corpus-update
pwa-content-story-corpus-check:
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.content_story_corpus check

pwa-content-story-corpus-update:
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.content_story_corpus write

.PHONY: pwa-schema-check pwa-schema-update pwa-schema-live-check pwa-schema-live-update
pwa-schema-check:
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.schema_inventory check

pwa-schema-update:
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.schema_inventory generate --write

pwa-schema-live-check:
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.schema_inventory check-live --database db/vmsh.db

pwa-schema-live-update:
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.schema_inventory report-live --database db/vmsh.db --write

.PHONY: pwa-auth-preflight-check pwa-auth-preflight-update pwa-workload-profile-check pwa-workload-profile-update pwa-baseline-check
pwa-auth-preflight-check:
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.auth_preflight check

pwa-auth-preflight-update:
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.auth_preflight write

.PHONY: pwa-auth-import-inventory pwa-auth-import-preview pwa-auth-import-apply
pwa-auth-import-inventory:
	@test -n "$(PWA_AUTH_IMPORT_DATABASE)" || (echo "Set PWA_AUTH_IMPORT_DATABASE to an explicit migrated disposable copy"; exit 2)
	@test -n "$(PWA_AUTH_IMPORT_REPORT)" || (echo "Set PWA_AUTH_IMPORT_REPORT"; exit 2)
	@test -n "$(PWA_AUTH_IMPORT_DETAIL_REPORT)" || (echo "Set PWA_AUTH_IMPORT_DETAIL_REPORT below .runtime"; exit 2)
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.auth_import inventory --database "$(PWA_AUTH_IMPORT_DATABASE)" --report "$(PWA_AUTH_IMPORT_REPORT)" --detail-report "$(PWA_AUTH_IMPORT_DETAIL_REPORT)"

pwa-auth-import-preview:
	@test -n "$(PWA_AUTH_IMPORT_DATABASE)" || (echo "Set PWA_AUTH_IMPORT_DATABASE to an explicit migrated disposable copy"; exit 2)
	@test -n "$(PWA_AUTH_IMPORT_DECISIONS)" || (echo "Set PWA_AUTH_IMPORT_DECISIONS to an owner-only JSON file"; exit 2)
	@test -n "$(PWA_AUTH_IMPORT_REPORT)" || (echo "Set PWA_AUTH_IMPORT_REPORT"; exit 2)
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.auth_import preview --database "$(PWA_AUTH_IMPORT_DATABASE)" --decisions "$(PWA_AUTH_IMPORT_DECISIONS)" --report "$(PWA_AUTH_IMPORT_REPORT)"

pwa-auth-import-apply:
	@test -n "$(PWA_AUTH_IMPORT_DATABASE)" || (echo "Set PWA_AUTH_IMPORT_DATABASE to an explicit migrated disposable copy"; exit 2)
	@test -n "$(PWA_AUTH_IMPORT_CONFIRM_DATABASE)" || (echo "Set PWA_AUTH_IMPORT_CONFIRM_DATABASE to the same exact path"; exit 2)
	@test -n "$(PWA_AUTH_IMPORT_DECISIONS)" || (echo "Set PWA_AUTH_IMPORT_DECISIONS to an owner-only JSON file"; exit 2)
	@test -n "$(PWA_AUTH_IMPORT_REPORT)" || (echo "Set PWA_AUTH_IMPORT_REPORT"; exit 2)
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.auth_import apply --database "$(PWA_AUTH_IMPORT_DATABASE)" --confirm-database "$(PWA_AUTH_IMPORT_CONFIRM_DATABASE)" --decisions "$(PWA_AUTH_IMPORT_DECISIONS)" --report "$(PWA_AUTH_IMPORT_REPORT)"

pwa-workload-profile-check:
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.workload_profile check

pwa-workload-profile-update:
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.workload_profile write

pwa-baseline-check: pwa-golden-check pwa-content-story-corpus-check pwa-schema-check pwa-schema-live-check pwa-auth-preflight-check pwa-workload-profile-check

.PHONY: pwa-s3-live-smoke pwa-content-assets-live-smoke pwa-written-attachment-live-smoke
pwa-s3-live-smoke:
	@test "$(VMSH_ENABLE_LIVE_S3_TEST)" = "true" || (echo "Set VMSH_ENABLE_LIVE_S3_TEST=true"; exit 2)
	@test -n "$(PWA_S3_RUN_ID)" || (echo "Set a unique lowercase PWA_S3_RUN_ID"; exit 2)
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.storage_smoke --run-id "$(PWA_S3_RUN_ID)"

pwa-content-assets-live-smoke:
	@test "$(VMSH_ENABLE_LIVE_S3_TEST)" = "true" || (echo "Set VMSH_ENABLE_LIVE_S3_TEST=true"; exit 2)
	@test -n "$(PWA_S3_RUN_ID)" || (echo "Set a unique lowercase PWA_S3_RUN_ID"; exit 2)
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.content_asset_storage_smoke --run-id "$(PWA_S3_RUN_ID)"

pwa-written-attachment-live-smoke:
	@test "$(VMSH_ENABLE_LIVE_S3_TEST)" = "true" || (echo "Set VMSH_ENABLE_LIVE_S3_TEST=true"; exit 2)
	@test -n "$(PWA_S3_RUN_ID)" || (echo "Set a unique lowercase PWA_S3_RUN_ID"; exit 2)
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.written_attachment_storage_smoke --run-id "$(PWA_S3_RUN_ID)"

.PHONY: pwa-nats-local-smoke pwa-telegram-bind-test-channel pwa-telegram-live-smoke pwa-telegram-rich-live-smoke
pwa-nats-local-smoke:
	$(PWA_UV_ENV) VMSH_RUN_LOCAL_NATS_SMOKE=1 uv run pytest -q -n0 pwa_tests/integration/test_nats_live.py

pwa-telegram-bind-test-channel:
	@test "$(VMSH_RUN_TELEGRAM_LIVE_SMOKE)" = "1" || (echo "Set VMSH_RUN_TELEGRAM_LIVE_SMOKE=1"; exit 2)
	@test -n "$(VMSH_TELEGRAM_TEST_CHANNEL_ID)" || (echo "Set the canonical negative VMSH_TELEGRAM_TEST_CHANNEL_ID"; exit 2)
	$(PWA_UV_ENV) VMSH_RUN_TELEGRAM_LIVE_SMOKE=1 VMSH_TELEGRAM_TEST_CHANNEL_ID="$(VMSH_TELEGRAM_TEST_CHANNEL_ID)" uv run python -m vmshpwa.scripts.telegram_test_capability --live --bind-channel --confirm vmsh179devbot-channel-synthetic

pwa-telegram-live-smoke:
	@test "$(VMSH_RUN_TELEGRAM_LIVE_SMOKE)" = "1" || (echo "Set VMSH_RUN_TELEGRAM_LIVE_SMOKE=1"; exit 2)
	@test -z "$(VMSH_TELEGRAM_TEST_CHANNEL_ID)" || (echo "Unset VMSH_TELEGRAM_TEST_CHANNEL_ID; smoke uses the verified local binding"; exit 2)
	$(PWA_UV_ENV) VMSH_RUN_TELEGRAM_LIVE_SMOKE=1 uv run python -m vmshpwa.scripts.telegram_test_capability --live --run-smoke --confirm vmsh179devbot-channel-synthetic

pwa-telegram-rich-live-smoke:
	@test "$(VMSH_RUN_TELEGRAM_LIVE_SMOKE)" = "1" || (echo "Set VMSH_RUN_TELEGRAM_LIVE_SMOKE=1"; exit 2)
	@test -z "$(VMSH_TELEGRAM_TEST_CHANNEL_ID)" || (echo "Unset VMSH_TELEGRAM_TEST_CHANNEL_ID; smoke uses the verified local binding"; exit 2)
	$(PWA_UV_ENV) VMSH_RUN_TELEGRAM_LIVE_SMOKE=1 uv run python -m vmshpwa.scripts.telegram_test_capability --live --run-rich-smoke --confirm vmsh179devbot-channel-synthetic

.PHONY: pwa-format pwa-lint pwa-typecheck pwa-test pwa-storybook-test pwa-build pwa-e2e pwa-e2e-auth pwa-e2e-content pwa-e2e-submissions pwa-e2e-functional pwa-e2e-realtime pwa-e2e-runtime pwa-visual pwa-visual-update telegram-history-test
pwa-format:
	cd $(PWA_DIR) && CI=true pnpm format

pwa-lint:
	cd $(PWA_DIR) && CI=true pnpm lint

pwa-typecheck:
	cd $(PWA_DIR) && CI=true pnpm typecheck

pwa-test:
	cd $(PWA_DIR) && CI=true pnpm test
	$(PWA_UV_ENV) $(PWA_E2E_ENV) uv run pytest -q -n0 pwa_tests

pwa-storybook-test:
	cd $(PWA_DIR) && CI=true pnpm storybook:test

pwa-build:
	cd $(PWA_DIR) && CI=true pnpm build

pwa-e2e:
	cd $(PWA_DIR) && CI=true pnpm e2e

pwa-e2e-auth:
	cd $(PWA_DIR) && CI=true pnpm e2e:auth

pwa-e2e-content:
	cd $(PWA_DIR) && CI=true pnpm e2e:content

pwa-e2e-submissions:
	cd $(PWA_DIR) && CI=true pnpm e2e:submissions

pwa-e2e-review:
	cd $(PWA_DIR) && CI=true pnpm e2e:review

pwa-e2e-functional:
	cd $(PWA_DIR) && CI=true pnpm e2e:functional

pwa-e2e-realtime:
	cd $(PWA_DIR) && CI=true pnpm e2e:realtime

pwa-e2e-runtime:
	cd $(PWA_DIR) && CI=true pnpm e2e:runtime-isolation

pwa-visual:
	cd $(PWA_DIR) && CI=true pnpm e2e:visual

pwa-visual-update:
	cd $(PWA_DIR) && CI=true pnpm e2e:visual:update

telegram-history-test:
	$(PWA_UV_ENV) VMSH_RUNTIME_PROFILE=telegram-history-test uv run pytest -q -n0 tests/test_telegram_test_submission_policy.py tests/test_handler_flows.py tests/test_admin_weekly_ops.py

.PHONY: pwa-nginx-check
pwa-nginx-check:
	$(PWA_UV_ENV) uv run python -m vmshpwa.scripts.nginx_config_check --config "$${VMSH_PWA_NGINX_CONFIG:-/etc/nginx/nginx.conf}" --site-config "$${VMSH_PWA_NGINX_SITE_CONFIG:-/etc/nginx/conf.d/vmshpwa.conf}" --public-host "$${VMSH_PWA_PUBLIC_HOST:-}"
