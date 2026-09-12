"""Public pure compiler surface for versioned PWA educational content."""

from .assets import (
    AssetConversionError,
    ConfiguredContentAssetConverter,
    ContentAssetConverter,
    ContentAssetTools,
    ConvertedAsset,
    prepare_tikz_standalone_document,
    sanitize_svg,
)
from .asset_service import ContentAssetService, PersistedContentAsset
from .compiler import COMPILER_VERSION, ContentCompileError, compile_latex
from .model import (
    CompileResult,
    ContentRole,
    Diagnostic,
    DiagnosticSeverity,
    DocumentAst,
    SourceEncoding,
)
from .scanner import ParserLimits
from .tikz import TikzScanIssue, TikzScanResult, TikzSource, scan_tikz_sources
from .telegram import (
    TELEGRAM_BOT_API_DIALECT,
    TelegramMarkupError,
    TelegramRichLimits,
    TelegramRichMetrics,
    sanitize_telegram_rich_html,
    validate_telegram_rich_html,
)
from .web_document import (
    WEB_CONTENT_CONTRACT_VERSION,
    WebAssetDescriptor,
    WebDocumentError,
    render_web_document,
)

__all__ = [
    "AssetConversionError",
    "COMPILER_VERSION",
    "CompileResult",
    "ConfiguredContentAssetConverter",
    "ContentCompileError",
    "ContentAssetConverter",
    "ContentAssetService",
    "ContentAssetTools",
    "ContentRole",
    "Diagnostic",
    "DiagnosticSeverity",
    "DocumentAst",
    "ConvertedAsset",
    "ParserLimits",
    "PersistedContentAsset",
    "SourceEncoding",
    "TELEGRAM_BOT_API_DIALECT",
    "TelegramMarkupError",
    "TelegramRichLimits",
    "TelegramRichMetrics",
    "compile_latex",
    "prepare_tikz_standalone_document",
    "scan_tikz_sources",
    "sanitize_telegram_rich_html",
    "sanitize_svg",
    "validate_telegram_rich_html",
    "WEB_CONTENT_CONTRACT_VERSION",
    "WebAssetDescriptor",
    "WebDocumentError",
    "render_web_document",
    "TikzScanIssue",
    "TikzScanResult",
    "TikzSource",
]
