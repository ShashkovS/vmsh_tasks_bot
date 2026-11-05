from __future__ import annotations

import pytest

from helpers.pwa.content import (
    ContentRole,
    TelegramMarkupError,
    compile_latex,
    validate_telegram_rich_html,
)


def test_owner_approved_rich_html_dialect_is_accepted() -> None:
    markup = """<a name="chapter-0"></a>
<b>bold</b><i>italic</i><u>underlined</u><s>strike</s><code>code</code>
<mark>marked</mark><sub>sub</sub><sup>sup</sup><tg-spoiler>spoiler</tg-spoiler>
<a href="#chapter-0">anchor</a><a href="https://t.me/">url</a>
<a href="mailto:user@example.com">mail</a><a href="tel:+123">phone</a>
<a href="tg://user?id=123456789">mention</a>
<tg-reference name="note-1">reference</tg-reference>
<tg-emoji emoji-id="5368324170671202286">👍</tg-emoji>
<img src="tg://emoji?id=5368324170671202286" alt="👍"/>
<tg-time unix="1647531900" format="wDT">tomorrow</tg-time><tg-math>x^2</tg-math>
<h1>H1</h1><h6>H6</h6><p>Paragraph</p>
<pre><code class="language-python">print(1)</code></pre><footer>Footer</footer><hr/>
<ul><li><input type="checkbox" checked/>Checked</li></ul>
<ol start="3" type="a" reversed><li value="7" type="i">Seventh</li></ol>
<blockquote><p>Quote</p><cite>Author</cite></blockquote>
<aside>Pull<cite>Author</cite></aside>
<img src="https://telegram.org/photo.jpg"/>
<video src="https://telegram.org/video.mp4"></video>
<audio src="https://telegram.org/audio.mp3"></audio>
<figure><img src="https://telegram.org/photo.jpg" tg-spoiler/><figcaption>Photo<cite>Credit</cite></figcaption></figure>
<tg-map lat="41.9" long="12.5" zoom="24"/>
<figure><tg-map lat="41.9" long="12.5" zoom="14"/><figcaption>Map</figcaption></figure>
<tg-collage><img src="https://telegram.org/a.jpg"/><video src="https://telegram.org/a.mp4"></video><figcaption>Album</figcaption></tg-collage>
<tg-slideshow><video src="https://telegram.org/a.mp4"></video><img src="https://telegram.org/a.jpg"/></tg-slideshow>
<table bordered striped><caption>Table</caption><tr><th>H</th><td colspan="2" rowspan="2" align="center" valign="middle">V</td></tr></table>
<details open><summary>Title</summary><p>Content</p></details>
<tg-math-block>E = mc^2</tg-math-block>"""

    normalized, metrics = validate_telegram_rich_html(markup)

    assert normalized
    assert metrics.maximum_table_columns == 3
    # Custom emoji and maps are not media attachments.
    assert metrics.media == 8
    assert metrics.maximum_nesting <= 16


@pytest.mark.parametrize(
    "markup",
    [
        "<script>alert(1)</script>",
        '<p onclick="x">x</p>',
        '<a href="javascript:alert(1)">x</a>',
        '<a href="https://user:pass@example.com">x</a>',
        '<a href="tg://resolve?domain=owner">x</a>',
        '<img src="file:///etc/passwd"/>',
        '<video src="tg://video?id=x"></video>',
        '<img src="tg://emoji?id=1" alt=""/>',
        "<!-- hidden -->",
        "<!DOCTYPE html>",
    ],
)
def test_malicious_or_unapproved_markup_is_rejected(markup: str) -> None:
    with pytest.raises(TelegramMarkupError):
        validate_telegram_rich_html(markup)


def test_named_and_numeric_entities_follow_bot_api_10_2() -> None:
    approved = (
        "&lt;&gt;&amp;&quot;&apos;&nbsp;&hellip;&mdash;&ndash;"
        "&lsquo;&rsquo;&ldquo;&rdquo;&#179;&#x1F44D;"
    )
    normalized, metrics = validate_telegram_rich_html(approved)

    assert normalized == approved.replace("&#x1F44D;", "&#128077;")
    assert metrics.utf8_characters == 15
    with pytest.raises(TelegramMarkupError):
        validate_telegram_rich_html("&copy;")


@pytest.mark.parametrize(
    "markup",
    [
        "<table><p>x</p></table>",
        "<table><tr></tr></table>",
        "<table><tr><td><p>x</p></td></tr></table>",
        "<ul><p>x</p></ul>",
        "<li>x</li>",
        "<details><p>x</p><summary>s</summary></details>",
        "<details><summary>a</summary><summary>b</summary></details>",
        '<figure><img src="https://example.com/a.jpg"/><p>x</p></figure>',
        '<figure><img src="https://example.com/a.jpg"/><figcaption>a</figcaption><figcaption>b</figcaption></figure>',
        '<figure><img src="https://example.com/a.jpg"/><video src="https://example.com/a.mp4"></video></figure>',
        '<tg-collage><audio src="https://example.com/a.mp3"></audio></tg-collage>',
        '<p><img src="https://example.com/a.jpg"/></p>',
        "<p><h2>x</h2></p>",
        '<a name="anchor">not empty</a>',
        '<code class="language-python">x</code>',
        '<audio src="https://example.com/a.mp3">text</audio>',
    ],
)
def test_invalid_rich_block_shapes_are_rejected(markup: str) -> None:
    with pytest.raises(TelegramMarkupError):
        validate_telegram_rich_html(markup)


def test_rich_message_character_block_nesting_media_and_table_boundaries() -> None:
    validate_telegram_rich_html("я" * 32_768)
    with pytest.raises(TelegramMarkupError, match="32768"):
        validate_telegram_rich_html("я" * 32_769)

    validate_telegram_rich_html("<p></p>" * 500)
    with pytest.raises(TelegramMarkupError, match="500 blocks"):
        validate_telegram_rich_html("<p></p>" * 501)

    validate_telegram_rich_html("<b>" * 16 + "x" + "</b>" * 16)
    with pytest.raises(TelegramMarkupError, match="depth 16"):
        validate_telegram_rich_html("<b>" * 17 + "x" + "</b>" * 17)

    media = '<img src="https://example.com/a.jpg"/>'
    validate_telegram_rich_html(media * 50)
    with pytest.raises(TelegramMarkupError, match="50 media"):
        validate_telegram_rich_html(media * 51)

    cells = "<td>x</td>" * 20
    validate_telegram_rich_html(f"<table><tr>{cells}</tr></table>")
    with pytest.raises(TelegramMarkupError, match="20 columns"):
        validate_telegram_rich_html(f"<table><tr>{cells}<td>x</td></tr></table>")


def test_block_and_media_metrics_match_rich_block_model() -> None:
    markup = (
        '<figure><img src="https://example.com/a.jpg"/><figcaption>C</figcaption></figure>'
        '<img src="tg://emoji?id=5368324170671202286" alt="👍"/>'
        '<figure><tg-map lat="1" long="2" zoom="3"/></figure>'
        "<table><tr><td>x</td><td>y</td></tr></table>"
    )
    _normalized, metrics = validate_telegram_rich_html(markup)

    # Two figures, table and its row. Figure wrappers map to one media/map
    # block each; cells/captions/custom emoji are not separate blocks.
    assert metrics.blocks == 4
    assert metrics.media == 1
    assert metrics.utf8_characters == 4  # caption, emoji alt and two cells


@pytest.mark.parametrize(
    ("accepted", "rejected"),
    [
        (
            '<tg-map lat="-90" long="180" zoom="24"/>',
            '<tg-map lat="-91" long="180" zoom="24"/>',
        ),
        (
            '<tg-map lat="90" long="-180" zoom="0"/>',
            '<tg-map lat="90" long="181" zoom="0"/>',
        ),
        (
            '<tg-emoji emoji-id="9223372036854775807">x</tg-emoji>',
            '<tg-emoji emoji-id="9223372036854775808">x</tg-emoji>',
        ),
        (
            '<table><tr><td colspan="20">x</td></tr></table>',
            '<table><tr><td colspan="21">x</td></tr></table>',
        ),
    ],
)
def test_numeric_attribute_ranges_are_explicit(accepted: str, rejected: str) -> None:
    validate_telegram_rich_html(accepted)
    with pytest.raises(TelegramMarkupError):
        validate_telegram_rich_html(rejected)


def test_compiler_generated_telegram_derivative_satisfies_same_validator() -> None:
    result = compile_latex(
        (
            "\\begin{document}\\задача Текст $x^2$ и $$y^2$$. \\кзадача\\end{document}"
        ).encode(),
        source_name="fixtures/generated.tex",
        role=ContentRole.CONDITION,
    )

    normalized, metrics = validate_telegram_rich_html(result.telegram.content)
    assert normalized == result.telegram.content
    assert metrics.blocks >= 3
    assert "telegram.derivative_invalid" not in {
        diagnostic.code for diagnostic in result.diagnostics
    }
