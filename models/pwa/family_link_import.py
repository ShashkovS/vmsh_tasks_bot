"""Pure parsing rules for the read-only Family-to-Student link preview.

The preview intentionally contains no account provisioning or password fields.
See Phase 9 in ``vmshpwa/dev/development-plan/13-phase-9-family-and-progress.md``.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

from models.pwa.admin_accounts import (
    InvalidManagedAccountChange,
    prepare_family_link_identity,
)


FAMILY_LINK_COLUMNS = (
    "family_username",
    "student_public_id",
    "relationship_label",
    "is_primary",
)
MAX_FAMILY_LINK_ROWS = 10_000
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_BOOLEAN_VALUES = {"0": False, "1": True, "false": False, "true": True}


@dataclass(frozen=True, slots=True)
class FamilyLinkImportRow:
    row_number: int
    family_username: str
    family_username_normalized: str
    student_public_id: str
    relationship_label: str
    is_primary: bool


@dataclass(frozen=True, slots=True)
class FamilyLinkImportDiagnostic:
    row_number: int | None
    code: str


@dataclass(frozen=True, slots=True)
class FamilyLinkImportParseResult:
    source_row_count: int
    rows: tuple[FamilyLinkImportRow, ...]
    diagnostics: tuple[FamilyLinkImportDiagnostic, ...]


def parse_family_link_csv(source: str) -> FamilyLinkImportParseResult:
    """Parse one small exact-header CSV without retaining duplicate links."""

    reader = csv.DictReader(io.StringIO(source))
    if (
        reader.fieldnames is None
        or len(reader.fieldnames) != len(FAMILY_LINK_COLUMNS)
        or set(reader.fieldnames) != set(FAMILY_LINK_COLUMNS)
    ):
        return FamilyLinkImportParseResult(
            source_row_count=0,
            rows=(),
            diagnostics=(FamilyLinkImportDiagnostic(None, "invalid_header"),),
        )

    rows: list[FamilyLinkImportRow] = []
    diagnostics: list[FamilyLinkImportDiagnostic] = []
    seen_links: set[tuple[str, str]] = set()
    source_row_count = 0

    for raw_row in reader:
        source_row_count += 1
        row_number = reader.line_num
        if source_row_count > MAX_FAMILY_LINK_ROWS:
            diagnostics.append(FamilyLinkImportDiagnostic(row_number, "too_many_rows"))
            break
        if raw_row.get(None) or any(
            raw_row.get(column) is None for column in FAMILY_LINK_COLUMNS
        ):
            diagnostics.append(FamilyLinkImportDiagnostic(row_number, "malformed_row"))
            continue

        try:
            family_username, normalized_username, relationship_label = (
                prepare_family_link_identity(
                    username=str(raw_row["family_username"]),
                    relationship_label=str(raw_row["relationship_label"]),
                )
            )
        except InvalidManagedAccountChange as error:
            diagnostics.append(FamilyLinkImportDiagnostic(row_number, str(error)))
            continue

        student_public_id = str(raw_row["student_public_id"]).strip()
        if _PUBLIC_ID.fullmatch(student_public_id) is None:
            diagnostics.append(
                FamilyLinkImportDiagnostic(row_number, "invalid_student_public_id")
            )
            continue
        boolean_text = str(raw_row["is_primary"]).strip().casefold()
        if boolean_text not in _BOOLEAN_VALUES:
            diagnostics.append(
                FamilyLinkImportDiagnostic(row_number, "invalid_is_primary")
            )
            continue

        identity = (normalized_username, student_public_id)
        if identity in seen_links:
            diagnostics.append(FamilyLinkImportDiagnostic(row_number, "duplicate_link"))
            continue
        seen_links.add(identity)
        rows.append(
            FamilyLinkImportRow(
                row_number=row_number,
                family_username=family_username,
                family_username_normalized=normalized_username,
                student_public_id=student_public_id,
                relationship_label=relationship_label,
                is_primary=_BOOLEAN_VALUES[boolean_text],
            )
        )

    if source_row_count == 0:
        diagnostics.append(FamilyLinkImportDiagnostic(None, "empty_file"))

    return FamilyLinkImportParseResult(
        source_row_count=source_row_count,
        rows=tuple(rows),
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "FAMILY_LINK_COLUMNS",
    "FamilyLinkImportDiagnostic",
    "FamilyLinkImportParseResult",
    "FamilyLinkImportRow",
    "MAX_FAMILY_LINK_ROWS",
    "parse_family_link_csv",
]
