"""File/link policy shared by uploads and RichDocument validation.

See vmshpwa/docs/rich-file-attachments.md and rich_file_routes.py.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote, unquote


MAX_RICH_FILE_BYTES = 50 * 1024 * 1024
RICH_FILE_MIME_TYPES = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odt": "application/vnd.oasis.opendocument.text",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "odp": "application/vnd.oasis.opendocument.presentation",
    "txt": "text/plain; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "zip": "application/zip",
    "7z": "application/x-7z-compressed",
    "rar": "application/vnd.rar",
}
_DIGEST = re.compile(r"[a-f0-9]{64}")
_LOCAL_FILE_URL = re.compile(r"/pwa-rich-files/([a-f0-9]{64})/([^/?#]+)")


class InvalidRichFile(ValueError):
    pass


def rich_file_name(value: str) -> str:
    """Keep one portable NFC basename, including its original extension."""

    filename = unicodedata.normalize("NFC", value.replace("\\", "/").rsplit("/", 1)[-1])
    filename = "".join(
        character
        for character in filename
        if unicodedata.category(character) not in {"Cc", "Cf"}
    ).strip()
    try:
        byte_size = len(filename.encode("utf-8"))
    except UnicodeEncodeError as error:
        raise InvalidRichFile("filename must be valid UTF-8") from error
    if not filename or byte_size > 255 or filename in {".", ".."}:
        raise InvalidRichFile("filename must contain 1..255 UTF-8 bytes")
    rich_file_mime_type(filename)
    return filename


def rich_file_mime_type(filename: str) -> str:
    extension = filename.rpartition(".")[2].casefold()
    try:
        return RICH_FILE_MIME_TYPES[extension]
    except KeyError:
        raise InvalidRichFile("file extension is not supported") from None


def rich_file_key(digest: str, filename: str) -> str:
    if not _DIGEST.fullmatch(digest) or rich_file_name(filename) != filename:
        raise InvalidRichFile("file key is not canonical")
    return f"rich-files/sha256/{digest[:2]}/{digest[2:4]}/{digest}/{filename}"


def local_rich_file_url(digest: str, filename: str) -> str:
    rich_file_key(digest, filename)
    return f"/pwa-rich-files/{digest}/{quote(filename, safe='')}"


def is_local_rich_file_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 4_096:
        return False
    match = _LOCAL_FILE_URL.fullmatch(value)
    if match is None:
        return False
    try:
        filename = unquote(match[2], errors="strict")
        return local_rich_file_url(match[1], filename) == value
    except InvalidRichFile, UnicodeError:
        return False
