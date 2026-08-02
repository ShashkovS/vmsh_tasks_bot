# Phase 6 proof: Telegram annotation composite

Date: 2026-08-02

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- `helpers/pwa/review_composite.py` converts one immutable submitted WebP plus
  its already-validated normalized annotation manifest into a PNG suitable for
  the Telegram adapter.
- The renderer supports the complete accepted mark vocabulary: pencil,
  eraser, text, arrow, rectangle and highlight, plus the four accepted colors
  and rotation by 0/90/180/270 degrees.
- Coordinates remain normalized in storage. The derivative scales positions by
  the image width/height and stroke/text sizes by the shorter edge, so the
  overlay remains aligned on portrait and landscape photographs.
- Eraser marks affect only the annotation layer. The original Student WebP is
  read as bytes and is never modified or replaced.
- Text is XML-escaped before it enters the temporary SVG. ImageMagick runs
  without a shell, with a 30-second bound; failures expose only a stable
  operation name and not private filenames or image diagnostics.
- The module deliberately does not query SQLite, choose recipients or call the
  Telegram API. Those remain responsibilities of the current Telegram adapter;
  this keeps the reusable image operation independent of delivery policy.

Implementation:

- `helpers/pwa/review_composite.py`;
- `pwa_tests/test_review_annotation_composite.py`;
- matching browser renderer:
  `vmshpwa/packages/product/src/review-annotation-surface.tsx`.

## Executable evidence

- Real ImageMagick test: creates a WebP, renders all supported mark kinds,
  rotates the result, verifies the PNG signature and `80 × 120` output, and
  proves the source SHA-256 is unchanged.
- Corrupt-image test proves the stable redacted `identify` failure.
- SVG unit test proves normalized dimensions, non-distorting canvas semantics,
  eraser mask, palette mapping and XML escaping.
- Review-composite plus toolchain suites: **12 passed**.
- Targeted Ruff check: **PASS**.
- Manual inspection of the generated 1200 × 800 derivative confirmed visible
  pencil/eraser, arrow, rectangle, highlight and escaped text alignment.
- `git diff --check`: **PASS** before commit.

This proof accepts the Telegram PNG derivative operation. It does not introduce
a second review-delivery workflow or replace the existing Telegram adapter.
