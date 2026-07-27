"""Build a privacy-safe workload profile from raw ``logs/events.jsonl*``.

Raw trace identifiers, flow identifiers, Telegram IDs and event payloads stay in
memory and are never rendered.  The profile distinguishes emitted records from
logical traces and labels all minute-level figures as workload proxies rather
than concurrent-session measurements.  See Phase 0 in
``vmshpwa/dev/development-plan/04-phase-0-baseline.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from vmshpwa.scripts.report_io import AtomicReportWriteError, atomic_write_text
from vmshpwa.scripts.safe_source import (
    SafeSourceError,
    SourceFingerprint,
    fingerprint,
    read_and_fingerprint,
    secure_open,
    verify_path_matches,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LOGS_ROOT = REPOSITORY_ROOT / "logs"
_RAW_EVENT_LOG_NAME = re.compile(r"events\.jsonl(?:\.\d{4}-\d{2}-\d{2})?")


def _raw_event_log_paths(root: Path) -> tuple[Path, ...]:
    # ``selected.jsonl`` is a PII-bearing, deliberately filtered derivative of
    # these files. Including it would double count selected people and bias the
    # workload profile, so only the raw logger basename and rotations qualify.
    return tuple(
        sorted(
            (
                path
                for path in root.iterdir()
                if _RAW_EVENT_LOG_NAME.fullmatch(path.name)
            ),
            key=lambda path: path.name,
        )
    )


JSON_REPORT = REPOSITORY_ROOT / "pwa_tests/reports/workload-profile.json"
MARKDOWN_REPORT = REPOSITORY_ROOT / "pwa_tests/reports/workload-profile.md"
SCHEMA_VERSION = 1

_KNOWN_EVENT_LABELS = frozenset(
    {
        "admin.broadcast.completed",
        "admin.command.invoked",
        "admin.data.sync",
        "admin.sleep_state.set",
        "admin.state.mass_reset",
        "auth.failed",
        "auth.signon_attempt",
        "auth.start",
        "auth.success",
        "callback.routed",
        "command.invoked",
        "queue.written.dequeued",
        "queue.written.discussion_added",
        "queue.written.enqueued",
        "queue.written.status_changed",
        "reaction.saved",
        "result.saved",
        "state.transition",
        "student.problem.selected",
        "student.results.requested",
        "student.sos.started",
        "student.sos.submitted",
        "student.test_answer.submitted",
        "student.written_solution.submitted",
        "student.waitlist.left",
        "teacher.oral_queue.requested",
        "teacher.oral_round.finished",
        "teacher.student_lookup",
        "teacher.written_check.started",
        "teacher.written_queue.requested",
        "teacher.written_verdict.saved",
        "teacher.zoom_queue.viewed",
        "update.callback.received",
        "update.handler.error",
        "update.message.received",
        "user.group.changed",
        "user.mode.changed",
        "queue.waitlist.entered",
        "queue.waitlist.left",
        "trace.emit.error",
        "zoom.conversation.check_time_updated",
        "zoom.conversation.started",
        "zoom.queue.changed",
        "zoom.webhook.received",
    }
)
_KNOWN_SOURCE_LABELS = frozenset(
    {"tg.callback", "tg.message", "trace", "unknown", "zoom.webhook"}
)
_KNOWN_ACTOR_LABELS = frozenset(
    {
        "admin",
        "anonymous",
        "deactivated_student",
        "deleted_user",
        "student",
        "teacher",
        "teacher_admin",
        "unknown",
        "unknown_user",
    }
)
_LEGACY_NUMERIC_ACTOR_LABELS = {
    "-4": "unknown_user",
    "-2": "deactivated_student",
    "-1": "deleted_user",
    "1": "student",
    "2": "teacher",
    "128": "admin",
}
_INGRESS_EVENTS = {
    "update.message.received",
    "update.callback.received",
    "zoom.webhook.received",
}
_SUBMISSION_EVENTS = {
    "student.test_answer.submitted",
    "student.written_solution.submitted",
    "student.sos.submitted",
}
_REVIEW_COMPLETION_EVENTS = {
    "teacher.written_verdict.saved",
    "teacher.oral_round.finished",
}


class WorkloadProfileError(RuntimeError):
    """Raised for changing sources, unsafe paths or stale reports."""


@dataclass(frozen=True, slots=True)
class _Record:
    canonical_hash: bytes
    event: str
    event_label_status: str
    source: str
    source_label_status: str
    actor_type: str
    actor_label_status: str
    trace_id: str | None
    flow_id: str | None
    timestamp: datetime | None
    timezone_kind: str | None
    ok: bool | None
    photo_count: int | None
    has_document: bool | None
    document_size: int | None
    media_group_id: str | None
    written_count: int | None
    sos_count: int | None
    selected_count: int | None
    bad_count: int | None
    errors_count: int | None


@dataclass(frozen=True, slots=True)
class _FileRead:
    path: Path
    line_count: int
    invalid_json_count: int
    invalid_record_count: int
    invalid_timestamp_count: int
    records: tuple[_Record, ...]
    line_hashes: frozenset[bytes]


@dataclass(frozen=True, slots=True)
class _SourceSnapshot:
    path: Path
    descriptor: int
    fingerprint: SourceFingerprint
    content: bytes


@contextmanager
def _source_snapshots(sources: tuple[Path, ...]):
    try:
        with ExitStack() as stack:
            snapshots: list[_SourceSnapshot] = []
            for path in sources:
                descriptor = stack.enter_context(secure_open(path))
                source_fingerprint, content = read_and_fingerprint(descriptor)
                verify_path_matches(path, source_fingerprint)
                snapshots.append(
                    _SourceSnapshot(path, descriptor, source_fingerprint, content)
                )

            identities = [
                (snapshot.fingerprint.device, snapshot.fingerprint.inode)
                for snapshot in snapshots
            ]
            if len(set(identities)) != len(identities):
                raise WorkloadProfileError(
                    "The same workload inode was provided through multiple paths"
                )

            yield tuple(snapshots)

            for snapshot in snapshots:
                after = fingerprint(snapshot.descriptor)
                verify_path_matches(snapshot.path, after)
                if snapshot.fingerprint != after:
                    raise WorkloadProfileError(
                        "The workload source set changed while it was being read"
                    )
    except SafeSourceError as error:
        raise WorkloadProfileError(str(error)) from error


def _safe_label(
    value: Any, *, allowed: frozenset[str], fallback: str
) -> tuple[str, str]:
    if isinstance(value, str) and value in allowed:
        return value, "reviewed"
    return fallback, "missing" if value is None else "unreviewed"


def _actor_label(value: Any) -> tuple[str, str]:
    if isinstance(value, str) and value in _KNOWN_ACTOR_LABELS:
        return value, "reviewed"
    numeric = None
    if isinstance(value, str):
        numeric = value.strip()
    elif isinstance(value, int) and not isinstance(value, bool):
        numeric = str(value)
    if numeric in _LEGACY_NUMERIC_ACTOR_LABELS:
        return _LEGACY_NUMERIC_ACTOR_LABELS[numeric], "legacyNumericMapped"
    return "other-actor", "missing" if value is None else "unreviewed"


def _optional_nonnegative_int(value: Any) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else None
    )


def _parse_timestamp(value: Any) -> tuple[datetime | None, str | None]:
    if not isinstance(value, str):
        return None, None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, None
    if parsed.tzinfo is None:
        return parsed, "naive-local-timezone-unknown"
    return parsed.astimezone(timezone.utc).replace(
        tzinfo=None
    ), "explicit-offset-normalized-utc"


def _read_log(path: Path, content: bytes) -> _FileRead:
    records: list[_Record] = []
    line_hashes: set[bytes] = set()
    line_count = invalid_json_count = invalid_record_count = invalid_timestamp_count = 0

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise WorkloadProfileError("Workload source is not valid UTF-8") from error
    for raw_line in text.splitlines(keepends=True):
        line_count += 1
        line_hashes.add(
            hashlib.sha256(raw_line.rstrip("\r\n").encode("utf-8")).digest()
        )
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            invalid_json_count += 1
            continue
        if not isinstance(payload, dict):
            invalid_record_count += 1
            continue

        timestamp, timezone_kind = _parse_timestamp(payload.get("ts"))
        if timestamp is None:
            invalid_timestamp_count += 1
        trace_id = payload.get("trace_id")
        flow_id = payload.get("flow_id")
        event, event_label_status = _safe_label(
            payload.get("event"),
            allowed=_KNOWN_EVENT_LABELS,
            fallback="other-event",
        )
        source_label, source_label_status = _safe_label(
            payload.get("source"),
            allowed=_KNOWN_SOURCE_LABELS,
            fallback="other-source",
        )
        actor_type, actor_label_status = _actor_label(payload.get("actor_type"))
        records.append(
            _Record(
                canonical_hash=hashlib.sha256(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).digest(),
                event=event,
                event_label_status=event_label_status,
                source=source_label,
                source_label_status=source_label_status,
                actor_type=actor_type,
                actor_label_status=actor_label_status,
                trace_id=trace_id if isinstance(trace_id, str) else None,
                flow_id=flow_id if isinstance(flow_id, str) else None,
                timestamp=timestamp,
                timezone_kind=timezone_kind,
                ok=(payload.get("ok") if isinstance(payload.get("ok"), bool) else None),
                photo_count=_optional_nonnegative_int(payload.get("photo_count")),
                has_document=(
                    payload.get("has_document")
                    if isinstance(payload.get("has_document"), bool)
                    else None
                ),
                document_size=_optional_nonnegative_int(payload.get("doc_size")),
                media_group_id=(
                    str(payload["media_group_id"])
                    if payload.get("media_group_id") is not None
                    else None
                ),
                written_count=_optional_nonnegative_int(payload.get("written_count")),
                sos_count=_optional_nonnegative_int(payload.get("sos_count")),
                selected_count=_optional_nonnegative_int(payload.get("selected_count")),
                bad_count=_optional_nonnegative_int(payload.get("bad_count")),
                errors_count=_optional_nonnegative_int(payload.get("errors_count")),
            )
        )

    return _FileRead(
        path=path,
        line_count=line_count,
        invalid_json_count=invalid_json_count,
        invalid_record_count=invalid_record_count,
        invalid_timestamp_count=invalid_timestamp_count,
        records=tuple(records),
        line_hashes=frozenset(line_hashes),
    )


def _minute(timestamp: datetime) -> str:
    return timestamp.isoformat(timespec="minutes")


def _percentile(values: Iterable[float], percentile: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    rank = max(1, math.ceil(percentile * len(ordered)))
    return round(float(ordered[rank - 1]), 3)


def _peak(counter: Counter[str]) -> int:
    return max(counter.values(), default=0)


def _metrics(records: Iterable[_Record]) -> dict[str, Any]:
    materialized = tuple(records)
    event_counts = Counter(record.event for record in materialized)
    source_counts = Counter(record.source for record in materialized)
    actor_counts = Counter(record.actor_type for record in materialized)
    event_label_statuses = Counter(record.event_label_status for record in materialized)
    source_label_statuses = Counter(
        record.source_label_status for record in materialized
    )
    actor_label_statuses = Counter(record.actor_label_status for record in materialized)
    missing_actor_sources = Counter(
        record.source
        for record in materialized
        if record.actor_label_status == "missing"
    )
    timestamps = [
        record.timestamp for record in materialized if record.timestamp is not None
    ]
    timezone_kinds = {
        record.timezone_kind for record in materialized if record.timezone_kind
    }

    events_per_minute: Counter[str] = Counter()
    ingress_per_minute: Counter[str] = Counter()
    submissions_per_minute: Counter[str] = Counter()
    reviews_per_minute: Counter[str] = Counter()
    flow_minutes: defaultdict[str, set[str]] = defaultdict(set)
    trace_first: dict[str, datetime] = {}
    trace_last: dict[str, datetime] = {}
    trace_event_counts: Counter[str] = Counter()

    for record in materialized:
        if record.trace_id:
            trace_event_counts[record.trace_id] += 1
        if record.timestamp is None:
            continue
        minute = _minute(record.timestamp)
        events_per_minute[minute] += 1
        if record.event in _INGRESS_EVENTS:
            ingress_per_minute[minute] += 1
        if record.event in _SUBMISSION_EVENTS:
            submissions_per_minute[minute] += 1
        if record.event in _REVIEW_COMPLETION_EVENTS:
            reviews_per_minute[minute] += 1
        if record.flow_id:
            flow_minutes[minute].add(record.flow_id)
        if record.trace_id:
            trace_first[record.trace_id] = min(
                record.timestamp, trace_first.get(record.trace_id, record.timestamp)
            )
            trace_last[record.trace_id] = max(
                record.timestamp, trace_last.get(record.trace_id, record.timestamp)
            )

    trace_starts_per_minute = Counter(
        _minute(timestamp) for timestamp in trace_first.values()
    )
    trace_spans = [
        max(0.0, (trace_last[trace_id] - first).total_seconds())
        for trace_id, first in trace_first.items()
    ]

    ok_counts = Counter(
        "true" if record.ok is True else "false" if record.ok is False else "missing"
        for record in materialized
    )
    partial_signals = Counter()
    partial_record_count = 0
    for record in materialized:
        if record.ok is not True:
            continue
        has_partial_signal = False
        if record.bad_count is not None and record.bad_count > 0:
            partial_signals["positiveBadCountWithOkTrue"] += 1
            has_partial_signal = True
        if record.errors_count is not None and record.errors_count > 0:
            partial_signals["positiveErrorsCountWithOkTrue"] += 1
            has_partial_signal = True
        partial_record_count += has_partial_signal

    ingress_messages = [
        record for record in materialized if record.event == "update.message.received"
    ]
    written_submissions = [
        record
        for record in materialized
        if record.event == "student.written_solution.submitted"
    ]
    photo_message_proxies = [
        record for record in ingress_messages if (record.photo_count or 0) > 0
    ]
    written_photo_proxies = [
        record for record in written_submissions if (record.photo_count or 0) > 0
    ]
    variant_histogram = Counter(
        str(record.photo_count) for record in photo_message_proxies
    )
    media_groups = {
        record.media_group_id
        for record in written_submissions
        if record.media_group_id is not None
    }
    document_sizes = [
        record.document_size
        for record in written_submissions
        if record.document_size is not None
    ]

    queue_records = [
        record
        for record in materialized
        if record.event == "teacher.written_queue.requested"
    ]
    timezone_description = (
        next(iter(timezone_kinds)) if len(timezone_kinds) == 1 else "mixed-or-unknown"
    )
    return {
        "eventCount": len(materialized),
        "traceCount": len(trace_event_counts),
        "eventCounts": dict(sorted(event_counts.items())),
        "sourceCounts": dict(sorted(source_counts.items())),
        "actorTypeCounts": dict(sorted(actor_counts.items())),
        "labelQuality": {
            "event": {
                "reviewedRecords": event_label_statuses["reviewed"],
                "missingRecords": event_label_statuses["missing"],
                "unreviewedRecords": event_label_statuses["unreviewed"],
                "otherEventRecords": event_counts["other-event"],
            },
            "source": {
                "reviewedRecords": source_label_statuses["reviewed"],
                "missingRecords": source_label_statuses["missing"],
                "unreviewedRecords": source_label_statuses["unreviewed"],
                "otherSourceRecords": source_counts["other-source"],
            },
            "actor": {
                "reviewedRecords": actor_label_statuses["reviewed"],
                "legacyNumericMappedRecords": actor_label_statuses[
                    "legacyNumericMapped"
                ],
                "missingRecords": actor_label_statuses["missing"],
                "unreviewedRecords": actor_label_statuses["unreviewed"],
                "otherActorRecords": actor_counts["other-actor"],
                "missingBySafeSource": dict(sorted(missing_actor_sources.items())),
            },
        },
        "timeRange": {
            "firstObserved": min(timestamps).isoformat(timespec="milliseconds")
            if timestamps
            else None,
            "lastObserved": max(timestamps).isoformat(timespec="milliseconds")
            if timestamps
            else None,
            "timezoneSemantics": timezone_description,
        },
        "minuteProxies": {
            "observedMinuteBuckets": len(events_per_minute),
            "peakEventsPerMinute": _peak(events_per_minute),
            "peakTraceStartsPerMinute": _peak(trace_starts_per_minute),
            "peakIngressUpdatesPerMinute": _peak(ingress_per_minute),
            "peakSubmissionEventsPerMinute": _peak(submissions_per_minute),
            "peakReviewCompletionEventsPerMinute": _peak(reviews_per_minute),
            "peakDistinctFlowsPerMinute": max(
                (len(flows) for flows in flow_minutes.values()), default=0
            ),
        },
        "traceShape": {
            "singleEventTraces": sum(
                count == 1 for count in trace_event_counts.values()
            ),
            "multiEventTraces": sum(count > 1 for count in trace_event_counts.values()),
            "eventsPerTraceP50": _percentile(trace_event_counts.values(), 0.50),
            "eventsPerTraceP95": _percentile(trace_event_counts.values(), 0.95),
            "eventsPerTraceMax": max(trace_event_counts.values(), default=0),
            "observedSpanSecondsP50": _percentile(trace_spans, 0.50),
            "observedSpanSecondsP95": _percentile(trace_spans, 0.95),
            "observedSpanSecondsMax": round(max(trace_spans, default=0.0), 3),
            "spanIsNotRequestLatency": True,
        },
        "outcomeSignals": {
            "okTrueRecords": ok_counts["true"],
            "okFalseRecords": ok_counts["false"],
            "okMissingRecords": ok_counts["missing"],
            "okTruePartialSignalRecords": partial_record_count,
            "partialSignals": {
                key: partial_signals[key]
                for key in (
                    "positiveBadCountWithOkTrue",
                    "positiveErrorsCountWithOkTrue",
                )
            },
            "interpretation": (
                "ok defaults to true in emit_trace; positive bad_count/errors_count "
                "is therefore reported separately as partial success."
            ),
        },
        "media": {
            "photoCountFieldMeaning": "Telegram PhotoSize variants, not pages",
            "logicalPageCount": None,
            "logicalPhotoMessageProxyCount": len(photo_message_proxies),
            "writtenPhotoMessageProxyCount": len(written_photo_proxies),
            "photoSizeVariantHistogramAtIngress": dict(
                sorted(variant_histogram.items())
            ),
            "writtenMediaGroupCount": len(media_groups),
            "writtenDocumentMessageCount": sum(
                record.has_document is True for record in written_submissions
            ),
            "documentSizeObservationCount": len(document_sizes),
            "observedDocumentBytes": sum(document_sizes) if document_sizes else None,
            "photoBytes": None,
            "limitation": (
                "One photo message is a logical-photo proxy; albums emit multiple "
                "messages. Page count and compressed/original photo bytes are absent."
            ),
        },
        "queueDepthProxies": {
            "observationCount": len(queue_records),
            "maxReportedWrittenCount": max(
                (record.written_count or 0 for record in queue_records), default=0
            ),
            "maxReportedSosCount": max(
                (record.sos_count or 0 for record in queue_records), default=0
            ),
            "maxReportedSelectedCount": max(
                (record.selected_count or 0 for record in queue_records), default=0
            ),
            "outboxDepth": None,
        },
        "concurrency": {
            "directConcurrentSessions": None,
            "supportedProxies": [
                "peakTraceStartsPerMinute",
                "peakIngressUpdatesPerMinute",
                "peakDistinctFlowsPerMinute",
            ],
            "limitation": (
                "Trace logs contain emitted event times, not session intervals or "
                "complete request start/finish timing."
            ),
        },
        "writeLatency": None,
    }


def _deduplicate_records(records: Iterable[_Record]) -> tuple[_Record, ...]:
    unique: dict[bytes, _Record] = {}
    for record in records:
        unique.setdefault(record.canonical_hash, record)
    return tuple(unique.values())


def analyze_logs(paths: Iterable[Path]) -> dict[str, Any]:
    """Return deterministic aggregate metrics for unchanged JSONL sources."""

    supplied_paths = tuple(Path(path) for path in paths)
    symlinks = [path for path in supplied_paths if path.is_symlink()]
    if symlinks:
        raise WorkloadProfileError("Workload sources must not be symlinks")
    sources = tuple(sorted((path.resolve() for path in supplied_paths), key=str))
    if not sources:
        raise WorkloadProfileError("No JSONL workload sources were provided")
    if len(set(sources)) != len(sources):
        raise WorkloadProfileError("The same JSONL workload source was provided twice")
    with _source_snapshots(sources) as snapshots:
        reads = tuple(
            _read_log(snapshot.path, snapshot.content) for snapshot in snapshots
        )

    all_records = tuple(record for read in reads for record in read.records)
    unique_records = _deduplicate_records(all_records)
    total_line_count = sum(read.line_count for read in reads)
    unique_line_hashes = set().union(*(read.line_hashes for read in reads))
    duplicate_exact_lines = total_line_count - len(unique_line_hashes)
    duplicate_exact_events = len(all_records) - len(unique_records)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceUnchanged": True,
        "coverage": (
            "No completeness/selection metadata accompanies these files; metrics "
            "describe only observed records and are not season-wide forecasts."
        ),
        "semantics": {
            "rawRecord": "one physical JSONL line emitted or copied into a source",
            "metricsEvent": (
                "one canonical distinct valid JSON object after removing byte- or "
                "whitespace-equivalent duplicates"
            ),
            "trace": (
                "one distinct raw trace_id, normally one Telegram update or Zoom "
                "webhook, with zero or more downstream event records"
            ),
            "flow": (
                "raw user/chat grouping used only in memory; only distinct counts "
                "per minute are reported"
            ),
        },
        "files": [
            {
                "path": read.path.relative_to(REPOSITORY_ROOT).as_posix()
                if read.path.is_relative_to(REPOSITORY_ROOT)
                else f"external-test-fixture-{index:02d}",
                "lineCount": read.line_count,
                "exactDuplicateLineCount": read.line_count - len(read.line_hashes),
                "invalidJsonCount": read.invalid_json_count,
                "invalidRecordCount": read.invalid_record_count,
                "invalidTimestampCount": read.invalid_timestamp_count,
                "metrics": _metrics(_deduplicate_records(read.records)),
            }
            for index, read in enumerate(reads, start=1)
        ],
        "combined": {
            "rawLineCount": total_line_count,
            "exactDuplicateLineCount": duplicate_exact_lines,
            "exactDuplicateEventRecordCount": duplicate_exact_events,
            "metricsUseCanonicalRecordDeduplication": True,
            "metrics": _metrics(unique_records),
        },
    }


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def render_markdown(report: dict[str, Any]) -> str:
    metrics = report["combined"]["metrics"]
    minute = metrics["minuteProxies"]
    outcome = metrics["outcomeSignals"]
    media = metrics["media"]
    queue = metrics["queueDepthProxies"]
    labels = metrics["labelQuality"]
    source_lines = "\n".join(
        f"- `{item['path']}`: {item['lineCount']} lines, "
        f"{item['exactDuplicateLineCount']} exact duplicate lines, "
        f"{item['metrics']['eventCount']} events, "
        f"{item['metrics']['traceCount']} traces"
        for item in report["files"]
    )
    return f"""# Observed workload profile

Источники прочитаны без изменения; отчёт содержит только агрегаты. Raw events,
trace/flow IDs, user/chat/Telegram IDs и payload fragments не сохранялись.

{source_lines}

Полнота выборки неизвестна: у файлов нет season-wide coverage metadata.

## Безопасность и полнота labels

- unreviewed event labels: {labels["event"]["unreviewedRecords"]}
- unreviewed source labels: {labels["source"]["unreviewedRecords"]}
- legacy numeric actor labels, mapped через явную таблицу: {labels["actor"]["legacyNumericMappedRecords"]}
- actor label отсутствует: {labels["actor"]["missingRecords"]}
- unreviewed actor labels: {labels["actor"]["unreviewedRecords"]}
- missing actor by safe source: `{json.dumps(labels["actor"]["missingBySafeSource"], ensure_ascii=False, sort_keys=True)}`

Event/source/actor values сериализуются только после explicit allowlist. Неизвестное
значение становится `other-*`, поэтому динамическая строка или идентификатор не
может попасть в отчёт. Отсутствующий actor не считается неизвестной ролью:
например, Zoom webhook не всегда несёт user context.

## Raw record, metrics event и trace — разные единицы

- Raw record: одна физическая JSONL-строка.
- Metrics event: один canonical distinct valid JSON object после удаления
  byte/whitespace-equivalent duplicates.
- Trace: один distinct `trace_id`, обычно один Telegram update или Zoom webhook.
- Наблюдалось metrics events: {metrics["eventCount"]}; traces: {metrics["traceCount"]}.
- Raw lines: {report["combined"]["rawLineCount"]}; exact duplicate lines:
  {report["combined"]["exactDuplicateLineCount"]}.
- Canonically duplicate valid event records: {report["combined"]["exactDuplicateEventRecordCount"]}.
- Все combined metrics ниже рассчитаны после canonical JSON-record deduplication;
  порядок ключей и пробелы сериализации на identity не влияют.

## Minute-level proxies

- peak events/min: {minute["peakEventsPerMinute"]}
- peak trace starts/min: {minute["peakTraceStartsPerMinute"]}
- peak ingress updates/min: {minute["peakIngressUpdatesPerMinute"]}
- peak submission events/min: {minute["peakSubmissionEventsPerMinute"]}
- peak review completions/min: {minute["peakReviewCompletionEventsPerMinute"]}
- peak distinct flows/min: {minute["peakDistinctFlowsPerMinute"]}

Это не число одновременных сессий: session intervals и надёжные handler
start/finish timestamps отсутствуют. Observed trace span также не является
request/write latency. Write latency остаётся неизвестной.

## Outcomes

- `ok=true`: {outcome["okTrueRecords"]}
- `ok=false`: {outcome["okFalseRecords"]}
- `ok` missing: {outcome["okMissingRecords"]}
- `ok=true`, но есть partial-failure signal: {outcome["okTruePartialSignalRecords"]}

`emit_trace` по умолчанию выставляет `ok=true`; поэтому положительные
`bad_count`/`errors_count` считаются отдельно и не скрываются общей метрикой.

## Media

- `photo_count` — число Telegram `PhotoSize` variants, **не страниц**.
- photo-message proxy: {media["logicalPhotoMessageProxyCount"]}
- written photo-message proxy: {media["writtenPhotoMessageProxyCount"]}
- media groups: {media["writtenMediaGroupCount"]}
- logical page count: **неизвестно**
- photo bytes: **неизвестно**
- document size observations: {media["documentSizeObservationCount"]}

Один photo message можно считать только proxy одного изображения; Telegram album
приходит несколькими messages с общим media-group ID.

## Queue/outbox

- queue snapshots: {queue["observationCount"]}
- max reported written queue: {queue["maxReportedWrittenCount"]}
- max reported SOS queue: {queue["maxReportedSosCount"]}
- max selected batch: {queue["maxReportedSelectedCount"]}
- PWA outbox depth: **неизвестно**

Для этапа 11 всё ещё нужны server-side latency/SQLITE_BUSY metrics, media byte
telemetry, session concurrency и явно маркированное полное окно наблюдения.
"""


def _analyze_report_sources(paths: Iterable[Path] | None) -> dict[str, Any]:
    if paths is not None:
        return analyze_logs(paths)

    try:
        sources_before = _raw_event_log_paths(LOGS_ROOT)
    except OSError as error:
        raise WorkloadProfileError("Could not enumerate workload sources") from error
    report = analyze_logs(sources_before)
    try:
        sources_after = _raw_event_log_paths(LOGS_ROOT)
    except OSError as error:
        raise WorkloadProfileError("Could not re-enumerate workload sources") from error
    if tuple(path.name for path in sources_before) != tuple(
        path.name for path in sources_after
    ):
        raise WorkloadProfileError(
            "The default workload source membership changed while it was being read"
        )
    return report


def _atomic_write(path: Path, content: str) -> None:
    try:
        atomic_write_text(path, content)
    except AtomicReportWriteError as error:
        raise WorkloadProfileError(str(error)) from error


def write_reports(paths: Iterable[Path] | None = None) -> None:
    report = _analyze_report_sources(paths)
    _atomic_write(JSON_REPORT, render_json(report))
    _atomic_write(MARKDOWN_REPORT, render_markdown(report))


def validate_reports(paths: Iterable[Path] | None = None) -> None:
    report = _analyze_report_sources(paths)
    expected = {
        JSON_REPORT: render_json(report),
        MARKDOWN_REPORT: render_markdown(report),
    }
    for path, content in expected.items():
        try:
            committed = path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise WorkloadProfileError(
                f"Missing workload report: {path}; run "
                "`make pwa-workload-profile-update`"
            ) from error
        if committed != content:
            raise WorkloadProfileError(
                "Workload report is stale; inspect aggregate changes and run "
                "`make pwa-workload-profile-update` (or "
                "`python -m vmshpwa.scripts.workload_profile write`)"
            )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "write"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "write":
            write_reports()
            print("Wrote aggregate workload profile reports")
        else:
            validate_reports()
            print("Verified aggregate workload profile reports")
    except WorkloadProfileError as error:
        print(f"workload profile error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
