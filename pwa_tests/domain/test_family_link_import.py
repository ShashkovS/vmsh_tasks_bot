from models.pwa.family_link_import import FamilyLinkImportRow, parse_family_link_csv


HEADER = "family_username,student_public_id,relationship_label,is_primary\n"


def test_family_link_csv_normalizes_fields_and_rejects_duplicate_identity():
    result = parse_family_link_csv(
        HEADER
        + "  Family.One  ,student-one,  мама  ,TRUE\n"
        + "family.one,student-one,отец,0\n"
    )

    assert result.source_row_count == 2
    assert result.rows == (
        FamilyLinkImportRow(
            row_number=2,
            family_username="Family.One",
            family_username_normalized="family.one",
            student_public_id="student-one",
            relationship_label="мама",
            is_primary=True,
        ),
    )
    assert [(item.row_number, item.code) for item in result.diagnostics] == [
        (3, "duplicate_link")
    ]


def test_family_link_csv_reports_exact_structural_errors():
    wrong_header = parse_family_link_csv("family,student\na,b\n")
    assert [(item.row_number, item.code) for item in wrong_header.diagnostics] == [
        (None, "invalid_header")
    ]
    empty = parse_family_link_csv(HEADER)
    assert [(item.row_number, item.code) for item in empty.diagnostics] == [
        (None, "empty_file")
    ]

    result = parse_family_link_csv(
        HEADER
        + "family-one,Not Public,мама,true\n"
        + "family-two,student-two,отец,yes\n"
        + ",student-three,мама,false\n"
    )
    assert [(item.row_number, item.code) for item in result.diagnostics] == [
        (2, "invalid_student_public_id"),
        (3, "invalid_is_primary"),
        (4, "invalid_family_username"),
    ]
    assert result.rows == ()
