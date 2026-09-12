import pytest

from models.pwa.classrooms import InvalidClassroomName, prepare_classroom_name


def test_classroom_name_keeps_display_text_and_builds_nfkc_casefold_key():
    assert prepare_classroom_name("  Актовый зал  ") == (
        "Актовый зал",
        "актовый зал",
    )
    assert prepare_classroom_name("２０１") == ("２０１", "201")


@pytest.mark.parametrize("value", ["", "   ", "x" * 201, None])
def test_classroom_name_rejects_empty_too_long_or_non_text(value):
    with pytest.raises(InvalidClassroomName):
        prepare_classroom_name(value)
