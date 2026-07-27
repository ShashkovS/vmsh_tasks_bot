"""Strict serializer boundary for the owner-approved Telegram Rich dialect.

The dialect is recorded in ``vmshpwa/docs/latex-content-pipeline.md``.  It is
separate from legacy ``sendMessage(parse_mode=HTML)`` and this module performs
no Bot API calls.  Compiler output is passed through this validator as a
defence-in-depth postcondition before it can become a derivative.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit


class TelegramMarkupError(ValueError):
    """Raised when markup is outside the accepted Telegram Rich dialect."""


TELEGRAM_BOT_API_DIALECT = "10.2"


@dataclass(frozen=True)
class TelegramRichLimits:
    max_utf8_characters: int = 32_768
    max_blocks: int = 500
    max_nesting: int = 16
    max_media: int = 50
    max_table_columns: int = 20


@dataclass(frozen=True)
class TelegramRichMetrics:
    utf8_characters: int
    blocks: int
    maximum_nesting: int
    media: int
    maximum_table_columns: int


_VOID_TAGS = {"br", "hr", "img", "input", "tg-map"}
_ALLOWED_ATTRIBUTES: dict[str, frozenset[str]] = {
    "a": frozenset({"href", "name"}),
    "audio": frozenset({"src"}),
    "code": frozenset({"class"}),
    "details": frozenset({"open"}),
    "figure": frozenset(),
    "img": frozenset({"src", "alt", "tg-spoiler"}),
    "input": frozenset({"type", "checked"}),
    "li": frozenset({"value", "type"}),
    "ol": frozenset({"start", "type", "reversed"}),
    "table": frozenset({"bordered", "striped"}),
    "td": frozenset({"colspan", "rowspan", "align", "valign"}),
    "tg-emoji": frozenset({"emoji-id"}),
    "tg-map": frozenset({"lat", "long", "zoom"}),
    "tg-reference": frozenset({"name"}),
    "tg-time": frozenset({"unix", "format"}),
    "video": frozenset({"src", "tg-spoiler"}),
}
for _tag in {
    "aside",
    "b",
    "blockquote",
    "br",
    "caption",
    "cite",
    "del",
    "em",
    "figcaption",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "ins",
    "mark",
    "p",
    "pre",
    "s",
    "strike",
    "strong",
    "sub",
    "summary",
    "sup",
    "tg-collage",
    "tg-math",
    "tg-math-block",
    "tg-slideshow",
    "tg-spoiler",
    "th",
    "tr",
    "u",
    "ul",
}:
    _ALLOWED_ATTRIBUTES.setdefault(_tag, frozenset())

_BOOLEAN_ATTRIBUTES = {
    "bordered",
    "checked",
    "open",
    "reversed",
    "striped",
    "tg-spoiler",
}
_ANCHOR_NAME = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_INTEGER = re.compile(r"[0-9]{1,10}")
_UNSIGNED_INTEGER_64 = re.compile(r"[0-9]{1,19}")
_SIGNED_INTEGER = re.compile(r"-?[0-9]{1,20}")
_FLOAT = re.compile(r"-?(?:[0-9]{1,3})(?:\.[0-9]{1,8})?")
_FORMAT = re.compile(r"[A-Za-z0-9_.:+ -]{1,64}")
_CODE_CLASS = re.compile(r"language-[A-Za-z0-9_+.-]{1,40}")
_APPROVED_NAMED_ENTITIES = {
    "amp",
    "apos",
    "gt",
    "hellip",
    "ldquo",
    "lsquo",
    "lt",
    "mdash",
    "nbsp",
    "ndash",
    "quot",
    "rdquo",
    "rsquo",
}
_BLOCK_TAGS = {
    "aside",
    "blockquote",
    "details",
    "figure",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "table",
    "tg-collage",
    "tg-map",
    "tg-math-block",
    "tg-slideshow",
    "tr",
    "ul",
}
_MEDIA_TAGS = {"audio", "img", "video"}
_FIGURE_CONTENT_TAGS = _MEDIA_TAGS | {"tg-map"}


_INLINE_TAGS = {
    "a",
    "b",
    "code",
    "del",
    "em",
    "i",
    "ins",
    "mark",
    "s",
    "strike",
    "strong",
    "sub",
    "sup",
    "tg-emoji",
    "tg-math",
    "tg-reference",
    "tg-spoiler",
    "tg-time",
    "u",
}


def _safe_url(value: str, *, media: bool, allow_emoji: bool = False) -> bool:
    if not value or any(character in value for character in "\x00\r\n\t"):
        return False
    if value.startswith("#"):
        return not media and bool(_ANCHOR_NAME.fullmatch(value[1:]))
    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    if scheme in {"http", "https"}:
        return (
            bool(parsed.netloc) and parsed.username is None and parsed.password is None
        )
    if media:
        if not allow_emoji or scheme != "tg" or parsed.netloc != "emoji":
            return False
        query = parse_qs(parsed.query, strict_parsing=True)
        return (
            set(query) == {"id"}
            and len(query["id"]) == 1
            and _UNSIGNED_INTEGER_64.fullmatch(query["id"][0]) is not None
            and 1 <= int(query["id"][0]) < 2**63
        )
    if scheme in {"mailto", "tel"}:
        return bool(parsed.path)
    if scheme == "tg" and parsed.netloc == "user" and not parsed.path:
        query = parse_qs(parsed.query, strict_parsing=True)
        return (
            set(query) == {"id"}
            and len(query["id"]) == 1
            and _UNSIGNED_INTEGER_64.fullmatch(query["id"][0]) is not None
            and 1 <= int(query["id"][0]) < 2**63
        )
    return False


def _validated_attribute(tag: str, name: str, value: str | None) -> str:
    if name in _BOOLEAN_ATTRIBUTES:
        if value not in {None, "", name}:
            raise TelegramMarkupError(f"{tag}.{name} must be a boolean attribute")
        return name
    if value is None:
        raise TelegramMarkupError(f"{tag}.{name} requires a value")
    if name == "href" and not _safe_url(value, media=False):
        raise TelegramMarkupError("unsafe Telegram link URL")
    if name == "src" and not _safe_url(value, media=True, allow_emoji=tag == "img"):
        raise TelegramMarkupError("unsafe Telegram media URL")
    if name == "name" and not _ANCHOR_NAME.fullmatch(value):
        raise TelegramMarkupError("invalid Telegram anchor name")
    if name in {"start", "value", "colspan", "rowspan", "zoom", "emoji-id"}:
        integer_pattern = _UNSIGNED_INTEGER_64 if name == "emoji-id" else _INTEGER
        if not integer_pattern.fullmatch(value):
            raise TelegramMarkupError(f"{tag}.{name} must be a positive integer")
        number = int(value)
        if name in {"start", "value"} and not 1 <= number <= 2_147_483_647:
            raise TelegramMarkupError(f"{tag}.{name} is outside the supported range")
        if name == "colspan" and not 1 <= number <= 20:
            raise TelegramMarkupError("table colspan must be between 1 and 20")
        if name == "rowspan" and not 1 <= number <= 500:
            raise TelegramMarkupError("table rowspan must be between 1 and 500")
        if name == "zoom" and not 0 <= number <= 24:
            raise TelegramMarkupError("tg-map.zoom must be between 0 and 24")
        if name == "emoji-id" and not 1 <= number < 2**63:
            raise TelegramMarkupError(
                "tg-emoji.emoji-id is outside the supported range"
            )
    if name == "unix" and not _SIGNED_INTEGER.fullmatch(value):
        raise TelegramMarkupError("tg-time.unix must be an integer")
    if name == "unix" and not -(2**63) <= int(value) < 2**63:
        raise TelegramMarkupError("tg-time.unix is outside the supported range")
    if name in {"lat", "long"} and not _FLOAT.fullmatch(value):
        raise TelegramMarkupError(f"tg-map.{name} must be numeric")
    if name == "lat" and not -90 <= float(value) <= 90:
        raise TelegramMarkupError("tg-map.lat must be between -90 and 90")
    if name == "long" and not -180 <= float(value) <= 180:
        raise TelegramMarkupError("tg-map.long must be between -180 and 180")
    if name == "format" and not _FORMAT.fullmatch(value):
        raise TelegramMarkupError("tg-time.format is invalid")
    if name == "class" and not _CODE_CLASS.fullmatch(value):
        raise TelegramMarkupError("only language-* code classes are accepted")
    if name == "type":
        allowed = {"checkbox"} if tag == "input" else {"1", "a", "A", "i", "I"}
        if value not in allowed:
            raise TelegramMarkupError(f"unsupported {tag}.type")
    if name == "align" and value not in {"left", "center", "right"}:
        raise TelegramMarkupError("unsupported table alignment")
    if name == "valign" and value not in {"top", "middle", "bottom"}:
        raise TelegramMarkupError("unsupported table vertical alignment")
    return f'{name}="{html.escape(value, quote=True)}"'


class _StrictTelegramParser(HTMLParser):
    def __init__(self, limits: TelegramRichLimits):
        super().__init__(convert_charrefs=False)
        self.limits = limits
        self.output: list[str] = []
        self.stack: list[str] = []
        self.utf8_characters = 0
        self.blocks = 0
        self.maximum_nesting = 0
        self.media = 0
        self.maximum_table_columns = 0
        self._table_columns: list[int] = []
        self._children: list[list[str]] = []
        self._open_attribute_names: list[frozenset[str]] = []
        self._has_content: list[bool] = []

    def _check_limits(self) -> None:
        if self.utf8_characters > self.limits.max_utf8_characters:
            raise TelegramMarkupError(
                "Telegram Rich text exceeds 32768 UTF-8 characters"
            )
        if self.blocks > self.limits.max_blocks:
            raise TelegramMarkupError("Telegram Rich message exceeds 500 blocks")
        if self.maximum_nesting > self.limits.max_nesting:
            raise TelegramMarkupError("Telegram Rich message exceeds nesting depth 16")
        if self.media > self.limits.max_media:
            raise TelegramMarkupError("Telegram Rich message exceeds 50 media blocks")
        if self.maximum_table_columns > self.limits.max_table_columns:
            raise TelegramMarkupError("Telegram Rich table exceeds 20 columns")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        allowed = _ALLOWED_ATTRIBUTES.get(normalized)
        if allowed is None:
            raise TelegramMarkupError(f"unsupported Telegram tag <{normalized}>")
        normalized_attrs = [(name.lower(), value) for name, value in attrs]
        names = [name for name, _value in normalized_attrs]
        if len(names) != len(set(names)):
            raise TelegramMarkupError(f"duplicate attribute on <{normalized}>")
        if any(name not in allowed for name in names):
            unknown = next(name for name in names if name not in allowed)
            raise TelegramMarkupError(
                f"unsupported Telegram attribute {normalized}.{unknown}"
            )
        rendered = [
            _validated_attribute(normalized, name, value)
            for name, value in normalized_attrs
        ]
        attributes = f" {' '.join(rendered)}" if rendered else ""
        if normalized == "a" and len({"href", "name"} & set(names)) != 1:
            raise TelegramMarkupError("<a> requires exactly one of href or name")
        if normalized in {"img", "video", "audio"} and "src" not in names:
            raise TelegramMarkupError(f"<{normalized}> requires src")
        attr_values = dict(normalized_attrs)
        if normalized == "input" and attr_values.get("type") != "checkbox":
            raise TelegramMarkupError("only checkbox inputs are accepted")
        required_attributes = {
            "tg-emoji": {"emoji-id"},
            "tg-map": {"lat", "long", "zoom"},
            "tg-reference": {"name"},
            "tg-time": {"format", "unix"},
        }.get(normalized, set())
        if not required_attributes <= set(names):
            missing = sorted(required_attributes - set(names))[0]
            raise TelegramMarkupError(f"<{normalized}> requires {missing}")
        custom_emoji = normalized == "img" and attr_values.get("src", "").startswith(
            "tg://emoji?"
        )
        if custom_emoji and not attr_values.get("alt"):
            raise TelegramMarkupError("custom emoji <img> requires non-empty alt text")
        if normalized == "code" and "class" in names:
            parent = self.stack[-1] if self.stack else None
            if parent != "pre":
                raise TelegramMarkupError(
                    "language-* code class requires a <pre> parent"
                )
        parent = self.stack[-1] if self.stack else None
        self._validate_parent(normalized, parent, custom_emoji=custom_emoji)
        if self._children:
            self._children[-1].append("tg-emoji-img" if custom_emoji else normalized)
            self._has_content[-1] = True
        if self._counts_as_block(normalized, parent, names, custom_emoji=custom_emoji):
            self.blocks += 1
        if normalized in _MEDIA_TAGS and not custom_emoji:
            self.media += 1
        if custom_emoji:
            self.utf8_characters += len(attr_values["alt"])
        if normalized == "tr":
            self._table_columns.append(0)
        elif normalized in {"td", "th"} and self._table_columns:
            colspan = int(dict(attrs).get("colspan") or "1")
            self._table_columns[-1] += colspan
            self.maximum_table_columns = max(
                self.maximum_table_columns, self._table_columns[-1]
            )
        if normalized in _VOID_TAGS:
            self.output.append(f"<{normalized}{attributes}/>")
            self._check_limits()
            return
        self.output.append(f"<{normalized}{attributes}>")
        self.stack.append(normalized)
        self._children.append([])
        self._open_attribute_names.append(frozenset(names))
        self._has_content.append(False)
        self.maximum_nesting = max(self.maximum_nesting, len(self.stack))
        self._check_limits()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() not in _VOID_TAGS:
            raise TelegramMarkupError(f"non-void <{tag.lower()}/> is not accepted")
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in _VOID_TAGS:
            raise TelegramMarkupError(f"void <{normalized}> cannot have an end tag")
        if not self.stack or self.stack[-1] != normalized:
            raise TelegramMarkupError(f"unbalanced Telegram end tag </{normalized}>")
        children = self._children.pop()
        attribute_names = self._open_attribute_names.pop()
        has_content = self._has_content.pop()
        self._validate_children(
            normalized,
            children,
            attribute_names=attribute_names,
            has_content=has_content,
        )
        self.stack.pop()
        if normalized == "tr" and self._table_columns:
            self._table_columns.pop()
        self.output.append(f"</{normalized}>")

    def handle_data(self, data: str) -> None:
        if (
            data.strip()
            and self.stack
            and self.stack[-1] in {"table", "tr", "ul", "ol"}
        ):
            raise TelegramMarkupError(
                f"text is not allowed directly inside <{self.stack[-1]}>"
            )
        self.output.append(html.escape(data, quote=False))
        self.utf8_characters += len(data)
        if self._has_content and data:
            self._has_content[-1] = True
        self._check_limits()

    def handle_entityref(self, name: str) -> None:
        normalized = name.lower()
        if normalized not in _APPROVED_NAMED_ENTITIES:
            raise TelegramMarkupError(f"unsupported Telegram named entity &{name};")
        decoded = html.unescape(f"&{normalized};")
        self.output.append(f"&{normalized};")
        self.utf8_characters += len(decoded)
        if self._has_content:
            self._has_content[-1] = True
        self._check_limits()

    def handle_charref(self, name: str) -> None:
        try:
            codepoint = int(name[1:], 16) if name.lower().startswith("x") else int(name)
            character = chr(codepoint)
        except (ValueError, OverflowError) as error:
            raise TelegramMarkupError("invalid numeric character reference") from error
        if character == "\x00" or 0xD800 <= codepoint <= 0xDFFF:
            raise TelegramMarkupError("invalid Unicode character reference")
        self.output.append(f"&#{codepoint};")
        self.utf8_characters += 1
        if self._has_content:
            self._has_content[-1] = True
        self._check_limits()

    def handle_comment(self, data: str) -> None:
        raise TelegramMarkupError("HTML comments are not accepted")

    def handle_decl(self, decl: str) -> None:
        raise TelegramMarkupError("HTML declarations are not accepted")

    def unknown_decl(self, data: str) -> None:
        raise TelegramMarkupError("unknown HTML declarations are not accepted")

    def finish(self) -> tuple[str, TelegramRichMetrics]:
        if self.stack:
            raise TelegramMarkupError(f"unclosed Telegram tag <{self.stack[-1]}>")
        return "".join(self.output), TelegramRichMetrics(
            utf8_characters=self.utf8_characters,
            blocks=self.blocks,
            maximum_nesting=self.maximum_nesting,
            media=self.media,
            maximum_table_columns=self.maximum_table_columns,
        )

    @staticmethod
    def _validate_parent(tag: str, parent: str | None, *, custom_emoji: bool) -> None:
        if tag in {"caption", "tr"} and parent != "table":
            raise TelegramMarkupError(f"<{tag}> must be a direct child of <table>")
        if tag in {"td", "th"} and parent != "tr":
            raise TelegramMarkupError(f"<{tag}> must be a direct child of <tr>")
        if tag == "li" and parent not in {"ol", "ul"}:
            raise TelegramMarkupError("<li> must be a direct child of a list")
        if tag == "summary" and parent != "details":
            raise TelegramMarkupError("<summary> must be a direct child of <details>")
        if tag == "figcaption" and parent not in {
            "figure",
            "tg-collage",
            "tg-slideshow",
        }:
            raise TelegramMarkupError("<figcaption> has no supported media parent")
        if parent in {"table"} and tag not in {"caption", "tr"}:
            raise TelegramMarkupError("<table> accepts only caption and row blocks")
        if parent in {"tr"} and tag not in {"td", "th"}:
            raise TelegramMarkupError("<tr> accepts only table cells")
        if parent in {"ol", "ul"} and tag != "li":
            raise TelegramMarkupError("lists accept only direct <li> children")
        is_media_block = tag in _MEDIA_TAGS and not custom_emoji
        if parent in _INLINE_TAGS and (tag in _BLOCK_TAGS or is_media_block):
            raise TelegramMarkupError(
                f"block <{tag}> cannot be nested in inline <{parent}>"
            )
        if parent in {"p", "caption", "figcaption", "summary", "td", "th"} and (
            tag in _BLOCK_TAGS or is_media_block
        ):
            raise TelegramMarkupError(f"block <{tag}> cannot be nested in <{parent}>")
        if tag == "input" and parent != "li":
            raise TelegramMarkupError("checkbox <input> must be inside a list item")
        if tag == "cite" and parent not in {"aside", "blockquote", "figcaption"}:
            raise TelegramMarkupError(
                "<cite> has no supported quotation/caption parent"
            )
        if is_media_block and parent not in {
            None,
            "blockquote",
            "details",
            "figure",
            "li",
            "tg-collage",
            "tg-slideshow",
        }:
            raise TelegramMarkupError("media must be a separate rich-message block")

    @staticmethod
    def _counts_as_block(
        tag: str,
        parent: str | None,
        names: list[str],
        *,
        custom_emoji: bool,
    ) -> bool:
        """Mirror the Bot API block model, including nested blocks and rows.

        ``figure`` is only an HTML caption wrapper for its single media block,
        so it counts once and its direct media child does not count again.
        Captions, cells and summaries are rich text, not blocks.
        """

        if tag == "a":
            return "name" in names
        if tag == "figure":
            return True
        if tag == "tg-map" and parent == "figure":
            return False
        if tag in _MEDIA_TAGS:
            if custom_emoji:
                return False
            return parent != "figure"
        return tag in _BLOCK_TAGS

    @staticmethod
    def _validate_children(
        tag: str,
        children: list[str],
        *,
        attribute_names: frozenset[str],
        has_content: bool,
    ) -> None:
        if tag == "a" and "name" in attribute_names and has_content:
            raise TelegramMarkupError("named <a> anchors must be empty")
        if tag in {"audio", "video"} and has_content:
            raise TelegramMarkupError(f"media <{tag}> must be empty")
        if tag in {"tg-math", "tg-math-block"} and children:
            raise TelegramMarkupError(f"<{tag}> accepts raw LaTeX text only")
        if tag == "pre" and children not in ([], ["code"]):
            raise TelegramMarkupError("<pre> accepts plain text or one nested <code>")
        if tag == "details" and (not children or children[0] != "summary"):
            raise TelegramMarkupError("<details> must start with exactly one <summary>")
        if tag == "details" and children.count("summary") != 1:
            raise TelegramMarkupError("<details> must contain exactly one <summary>")
        if tag == "table":
            if children.count("caption") > 1:
                raise TelegramMarkupError("<table> accepts at most one caption")
            if "caption" in children and children[0] != "caption":
                raise TelegramMarkupError("table caption must be the first child")
            if "tr" not in children:
                raise TelegramMarkupError("<table> must contain at least one row")
        if tag == "tr" and not children:
            raise TelegramMarkupError("<tr> must contain at least one cell")
        if tag == "figure":
            media = [child for child in children if child in _FIGURE_CONTENT_TAGS]
            if len(media) != 1:
                raise TelegramMarkupError(
                    "<figure> must contain exactly one media block"
                )
            if children[0] not in _FIGURE_CONTENT_TAGS:
                raise TelegramMarkupError("figure media must be its first child")
            if children.count("figcaption") > 1:
                raise TelegramMarkupError("<figure> accepts at most one caption")
            if "figcaption" in children and children[-1] != "figcaption":
                raise TelegramMarkupError("figure caption must be its last child")
            if any(
                child not in _FIGURE_CONTENT_TAGS | {"figcaption"} for child in children
            ):
                raise TelegramMarkupError("<figure> contains an unsupported child")
        if tag in {"tg-collage", "tg-slideshow"}:
            media = [child for child in children if child in {"img", "video"}]
            if not media:
                raise TelegramMarkupError(f"<{tag}> requires image or video media")
            if any(child not in {"img", "video", "figcaption"} for child in children):
                raise TelegramMarkupError(f"<{tag}> contains an unsupported child")
            if "figcaption" in children and children[-1] != "figcaption":
                raise TelegramMarkupError(f"<{tag}> caption must be last")


def validate_telegram_rich_html(
    markup: str,
    *,
    limits: TelegramRichLimits | None = None,
) -> tuple[str, TelegramRichMetrics]:
    """Validate and canonically serialize exactly the accepted Rich subset."""

    parser = _StrictTelegramParser(limits or TelegramRichLimits())
    try:
        parser.feed(markup)
        parser.close()
    except (UnicodeError, ValueError) as error:
        if isinstance(error, TelegramMarkupError):
            raise
        raise TelegramMarkupError("malformed Telegram Rich markup") from error
    return parser.finish()


def sanitize_telegram_rich_html(
    markup: str, *, limits: TelegramRichLimits | None = None
) -> str:
    sanitized, _metrics = validate_telegram_rich_html(markup, limits=limits)
    return sanitized
