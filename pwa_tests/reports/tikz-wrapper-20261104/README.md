# Composite TikZ wrappers — 4 November 2026

Application commit `e0666d3e6de68eacb1e2e3309942a0806b1ada61`.
The `usl-08-n.tex` report failed with `Missing \endgroup inserted` at the
closing brace of a resizebox around a two-row tabular containing TikZ pictures.
The standalone class's `tikz` option captures each nested picture separately.
The converter now captures the whole source as one page and loads TikZ explicitly.

[Implementation](../../../helpers/pwa/content/assets.py),
[contract](../../../vmshpwa/docs/content-compiler-support-matrix.md#assets-и-внешний-toolchain),
[real regression test](../../integration/test_content_assets_smoke.py).
Both differently colored table rows must survive conversion of PDF page 1.

Validation: 42 focused domain/toolchain tests passed. All eight original figures
in the supplied local file and the composite table reconstructed from its first
two figures converted successfully; both rows of the preview were inspected.
No broad PWA/Storybook/E2E gate was run, following the owner's instruction.

Deployed on both production hosts under the existing two-site authorization.
The composite table and a Cyrillic-label probe passed with each production
toolchain; all 25 read-only HTTP checks passed per site. Verified online backups
preceded graceful worker replacement. Schema, canonical config, frontend static
symlinks, NATS and VMSh's three local metadata-repair files were preserved.

[VMSh receipt](vmsh-production.json), [TLF receipt](tlf-production.json).
Private scripts, backups and logs remain on each host under
`/web/vmsh_tasks_bot/deploy/releases/tikz-wrapper-20261104-e0666d3e6de6/`.
Ordinary Git transport only; rollback retains unrelated changes with
`git reset --keep` and replaces workers without restoring a stale database.
