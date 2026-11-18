from models.pwa.local_news import parse_telegram_markdown


def test_local_news_markdown_preserves_plain_text_and_supported_marks() -> None:
    plain, nodes = parse_telegram_markdown(
        "**Важно**: _сегодня_ ~~не~~ будет ||спойлер||, "
        "`код` и [ссылка](https://example.org)."
    )

    assert plain == "Важно: сегодня не будет спойлер, код и ссылка."
    assert [node.get("marks", [{}])[0].get("type") for node in nodes if "marks" in node] == [
        "bold",
        "italic",
        "strike",
        "spoiler",
        "code",
        "link",
    ]
    assert nodes[-2]["marks"] == [{"type": "link", "href": "https://example.org"}]


def test_local_news_markdown_keeps_unclosed_marker_literal() -> None:
    plain, nodes = parse_telegram_markdown("Текст **без закрытия")

    assert plain == "Текст **без закрытия"
    assert nodes == [{"type": "plain", "text": "Текст **без закрытия"}]
