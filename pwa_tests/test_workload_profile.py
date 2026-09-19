"""Aggregate-only tests for workload trace characterization."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

from vmshpwa.scripts import report_io, safe_source, workload_profile
from vmshpwa.scripts.report_io import AtomicReportWriteError, atomic_write_text
from vmshpwa.scripts.safe_source import secure_open
from vmshpwa.scripts.workload_profile import (
    WorkloadProfileError,
    _KNOWN_ACTOR_LABELS,
    _KNOWN_EVENT_LABELS,
    _KNOWN_SOURCE_LABELS,
    _analyze_report_sources,
    _raw_event_log_paths,
    analyze_logs,
    render_json,
    render_markdown,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _line(**payload) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _workload_fixture(first_path, second_path) -> tuple[str, str]:
    duplicated = _line(
        ts="2026-03-20T10:00:00.000",
        event="update.message.received",
        trace_id="private-trace-one",
        flow_id="private-flow-one",
        source="tg.message",
        actor_type="student",
        ok=True,
        photo_count=4,
        chat_id=123456,
        user_id=77,
        text="private raw message",
    )
    first_lines = [
        duplicated,
        _line(
            ts="2026-03-20T10:00:01.000",
            event="student.written_solution.submitted",
            trace_id="private-trace-one",
            flow_id="private-flow-one",
            source="tg.message",
            actor_type="student",
            ok=True,
            photo_count=4,
            media_group_id="private-media-group",
        ),
        _line(
            ts="2026-03-20T10:00:20.000",
            event="update.callback.received",
            trace_id="private-trace-two",
            flow_id="private-flow-two",
            source="tg.callback",
            actor_type="teacher",
            ok=True,
        ),
        _line(
            ts="2026-03-20T10:00:21.000",
            event="admin.broadcast.completed",
            trace_id="private-trace-two",
            flow_id="private-flow-two",
            source="tg.callback",
            actor_type="teacher",
            ok=True,
            bad_count=2,
            errors_count=1,
        ),
        "{invalid json",
    ]
    second_lines = [
        json.dumps(json.loads(duplicated), ensure_ascii=False, sort_keys=True),
        _line(
            ts="2026-03-20T10:01:00.000",
            event="teacher.written_queue.requested",
            trace_id="private-trace-three",
            flow_id="private-flow-three",
            source="tg.callback",
            actor_type="teacher",
            ok=True,
            written_count=5,
            sos_count=1,
            selected_count=3,
        ),
        _line(
            ts="2026-03-20T10:01:01.000",
            event="teacher.written_verdict.saved",
            trace_id="private-trace-three",
            flow_id="private-flow-three",
            source="tg.callback",
            actor_type="teacher",
            ok=True,
        ),
        _line(
            ts="2026-03-20T10:01:02.000",
            event="update.handler.error",
            trace_id="private-trace-four",
            flow_id="private-flow-four",
            source="tg.message",
            actor_type="student",
            ok=False,
            error_short="private exception text",
        ),
        _line(
            ts="2026-03-20T10:01:03.000",
            event="admin.data.sync",
            trace_id="private-trace-five",
            flow_id="private-flow-five",
            source="tg.message",
            actor_type="teacher",
            ok=True,
            errors_count=1,
        ),
        _line(
            ts="2026-03-20T10:01:04.000",
            event="student.written_solution.submitted",
            trace_id="private-trace-six",
            flow_id="private-flow-six",
            source="tg.message",
            actor_type="student",
            ok=True,
            has_document=True,
            doc_size=100,
        ),
    ]
    first_path.write_text("\n".join(first_lines) + "\n", encoding="utf-8")
    second_path.write_text("\n".join(second_lines) + "\n", encoding="utf-8")
    return duplicated, "private raw message"


def test_workload_profile_separates_events_traces_media_and_partial_success(tmp_path):
    first_path = tmp_path / "first.jsonl"
    second_path = tmp_path / "second.jsonl"
    _workload_fixture(first_path, second_path)
    before = (first_path.read_bytes(), second_path.read_bytes())

    report = analyze_logs((first_path, second_path))
    metrics = report["combined"]["metrics"]

    assert (first_path.read_bytes(), second_path.read_bytes()) == before
    assert report["sourceUnchanged"] is True
    assert report["combined"] | {"metrics": None} == {
        "rawLineCount": 11,
        "exactDuplicateLineCount": 0,
        "exactDuplicateEventRecordCount": 1,
        "metricsUseCanonicalRecordDeduplication": True,
        "metrics": None,
    }
    assert metrics["eventCount"] == 9
    assert metrics["traceCount"] == 6
    assert metrics["minuteProxies"] == {
        "observedMinuteBuckets": 2,
        "peakEventsPerMinute": 5,
        "peakTraceStartsPerMinute": 4,
        "peakIngressUpdatesPerMinute": 2,
        "peakSubmissionEventsPerMinute": 1,
        "peakReviewCompletionEventsPerMinute": 1,
        "peakDistinctFlowsPerMinute": 4,
    }
    assert metrics["outcomeSignals"]["okTrueRecords"] == 8
    assert metrics["outcomeSignals"]["okFalseRecords"] == 1
    assert metrics["outcomeSignals"]["okTruePartialSignalRecords"] == 2
    assert metrics["outcomeSignals"]["partialSignals"] == {
        "positiveBadCountWithOkTrue": 1,
        "positiveErrorsCountWithOkTrue": 2,
    }

    media = metrics["media"]
    assert media["photoCountFieldMeaning"] == "Telegram PhotoSize variants, not pages"
    assert media["logicalPageCount"] is None
    assert media["logicalPhotoMessageProxyCount"] == 1
    assert media["writtenPhotoMessageProxyCount"] == 1
    assert media["photoSizeVariantHistogramAtIngress"] == {"4": 1}
    assert media["writtenMediaGroupCount"] == 1
    assert media["writtenDocumentMessageCount"] == 1
    assert media["documentSizeObservationCount"] == 1
    assert media["observedDocumentBytes"] == 100
    assert media["photoBytes"] is None

    queue = metrics["queueDepthProxies"]
    assert queue == {
        "observationCount": 1,
        "maxReportedWrittenCount": 5,
        "maxReportedSosCount": 1,
        "maxReportedSelectedCount": 3,
        "outboxDepth": None,
    }
    assert metrics["concurrency"]["directConcurrentSessions"] is None
    assert metrics["writeLatency"] is None


def test_workload_report_drops_identifiers_and_raw_payloads(tmp_path):
    first_path = tmp_path / "first.jsonl"
    second_path = tmp_path / "second.jsonl"
    _workload_fixture(first_path, second_path)
    report = analyze_logs((first_path, second_path))
    serialized = render_json(report) + render_markdown(report)

    for private_value in (
        "private-trace-one",
        "private-flow-one",
        "private-media-group",
        "private raw message",
        "private exception text",
        "123456",
    ):
        assert private_value not in serialized
    assert json.loads(render_json(report)) == report


def test_workload_report_maps_unreviewed_ascii_labels_to_safe_categories(tmp_path):
    path = tmp_path / "secret-person-name.jsonl"
    path.write_text(
        _line(
            ts="2026-03-20T10:00:00.000",
            event="private.person.event",
            source="private-user-123",
            actor_type="private-student-456",
            trace_id="private-trace",
            ok=True,
        )
        + "\n",
        encoding="utf-8",
    )

    report = analyze_logs((path,))
    serialized = render_json(report) + render_markdown(report)

    for private_value in (
        "secret-person-name",
        "private.person.event",
        "private-user-123",
        "private-student-456",
    ):
        assert private_value not in serialized
    assert report["combined"]["metrics"]["eventCounts"] == {"other-event": 1}
    assert report["combined"]["metrics"]["sourceCounts"] == {"other-source": 1}
    assert report["combined"]["metrics"]["actorTypeCounts"] == {"other-actor": 1}
    assert report["combined"]["metrics"]["labelQuality"] == {
        "event": {
            "reviewedRecords": 0,
            "missingRecords": 0,
            "unreviewedRecords": 1,
            "otherEventRecords": 1,
        },
        "source": {
            "reviewedRecords": 0,
            "missingRecords": 0,
            "unreviewedRecords": 1,
            "otherSourceRecords": 1,
        },
        "actor": {
            "reviewedRecords": 0,
            "legacyNumericMappedRecords": 0,
            "missingRecords": 0,
            "unreviewedRecords": 1,
            "otherActorRecords": 1,
            "missingBySafeSource": {},
        },
    }


def test_workload_profile_maps_legacy_numeric_and_explains_missing_actor(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(
            (
                _line(
                    ts="2026-03-20T10:00:00.000",
                    event="auth.success",
                    source="tg.message",
                    actor_type="1",
                ),
                _line(
                    ts="2026-03-20T10:00:01.000",
                    event="zoom.webhook.received",
                    source="zoom.webhook",
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = analyze_logs((path,))["combined"]["metrics"]

    assert metrics["actorTypeCounts"] == {"other-actor": 1, "student": 1}
    assert metrics["labelQuality"]["actor"] == {
        "reviewedRecords": 0,
        "legacyNumericMappedRecords": 1,
        "missingRecords": 1,
        "unreviewedRecords": 0,
        "otherActorRecords": 1,
        "missingBySafeSource": {"zoom.webhook": 1},
    }


def test_workload_metrics_deduplicate_exact_records_within_one_file(tmp_path):
    path = tmp_path / "events.jsonl"
    line = _line(
        ts="2026-03-20T10:00:00.000",
        event="update.message.received",
        trace_id="private-trace",
        source="tg.message",
        actor_type="student",
        ok=True,
    )
    path.write_text(f"{line}\n{line}\n", encoding="utf-8")

    report = analyze_logs((path,))

    assert report["files"][0]["exactDuplicateLineCount"] == 1
    assert report["combined"]["exactDuplicateEventRecordCount"] == 1
    assert report["combined"]["metrics"]["eventCount"] == 1


def test_default_source_selection_excludes_filtered_derivatives(tmp_path):
    for name in (
        "events.jsonl",
        "events.jsonl.2026-03-20",
        "events.jsonl.backup",
        "events.jsonl.2026-03-20.tmp",
        "selected.jsonl",
        "other.jsonl",
    ):
        (tmp_path / name).touch()

    assert [path.name for path in _raw_event_log_paths(tmp_path)] == [
        "events.jsonl",
        "events.jsonl.2026-03-20",
    ]


def test_workload_profile_refuses_symlink_source(tmp_path):
    target = tmp_path / "events.jsonl"
    alias = tmp_path / "events.jsonl.alias"
    target.write_text("{}\n", encoding="utf-8")
    alias.symlink_to(target)

    with pytest.raises(WorkloadProfileError, match="must not be symlinks"):
        analyze_logs((alias,))


def test_secure_source_uses_strongest_available_nofollow_flag(tmp_path, monkeypatch):
    source = tmp_path / "events.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    open_file = safe_source.os.open
    observed_flags: list[int] = []

    def capture_flags(path, flags):
        observed_flags.append(flags)
        return open_file(path, flags)

    monkeypatch.setattr(safe_source.os, "open", capture_flags)
    with secure_open(source):
        pass

    strongest = getattr(os, "O_NOFOLLOW_ANY", 0) or getattr(os, "O_NOFOLLOW", 0)
    assert strongest
    assert observed_flags[0] & strongest == strongest


def test_workload_profile_refuses_duplicate_hard_link_inodes(tmp_path):
    source = tmp_path / "events.jsonl"
    alias = tmp_path / "events.jsonl.2026-03-20"
    source.write_text("{}\n", encoding="utf-8")
    os.link(source, alias)

    with pytest.raises(WorkloadProfileError, match="hard-linked aliases"):
        analyze_logs((source, alias))


def test_workload_profile_fingerprints_the_whole_source_set(tmp_path, monkeypatch):
    first_path = tmp_path / "events.jsonl"
    second_path = tmp_path / "events.jsonl.2026-03-20"
    line = _line(
        ts="2026-03-20T10:00:00.000",
        event="update.message.received",
        source="tg.message",
        actor_type="student",
    )
    first_path.write_text(line + "\n", encoding="utf-8")
    second_path.write_text(line + "\n", encoding="utf-8")
    read_log = workload_profile._read_log

    def mutate_an_already_read_source(path, content):
        result = read_log(path, content)
        if path == first_path.resolve():
            first_path.write_text(
                line.replace("10:00:00", "10:00:01") + "\n", encoding="utf-8"
            )
        return result

    monkeypatch.setattr(workload_profile, "_read_log", mutate_an_already_read_source)

    with pytest.raises(WorkloadProfileError, match="changed"):
        analyze_logs((first_path, second_path))


def test_default_source_membership_is_rechecked_after_read(tmp_path, monkeypatch):
    first_path = tmp_path / "events.jsonl"
    second_path = tmp_path / "events.jsonl.2026-03-20"
    first_path.write_text(
        _line(
            ts="2026-03-20T10:00:00.000",
            event="update.message.received",
            source="tg.message",
            actor_type="student",
        )
        + "\n",
        encoding="utf-8",
    )
    calls = 0

    def changing_membership(_root):
        nonlocal calls
        calls += 1
        return (first_path,) if calls == 1 else (first_path, second_path)

    monkeypatch.setattr(workload_profile, "_raw_event_log_paths", changing_membership)

    with pytest.raises(WorkloadProfileError, match="membership changed"):
        _analyze_report_sources(None)


def _function_return_strings(tree: ast.AST, function_name: str) -> set[str]:
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    return {
        node.value.value
        for node in ast.walk(function)
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def test_trace_emitters_and_dynamic_middleware_labels_are_allowlisted():
    literal_events: set[str] = set()
    dynamic_event_arguments: list[ast.AST] = []
    for directory in ("helpers", "handlers", "apps", "models", "db_methods"):
        for path in sorted((REPOSITORY_ROOT / directory).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "emit_trace"
                    and node.args
                ):
                    continue
                argument = node.args[0]
                if isinstance(argument, ast.Constant) and isinstance(
                    argument.value, str
                ):
                    literal_events.add(argument.value)
                else:
                    dynamic_event_arguments.append(argument)

    assert literal_events <= _KNOWN_EVENT_LABELS
    assert len(dynamic_event_arguments) == 1
    dynamic = dynamic_event_arguments[0]
    assert (
        isinstance(dynamic, ast.Call)
        and isinstance(dynamic.func, ast.Name)
        and dynamic.func.id == "_command_event_name"
    )

    middleware_tree = ast.parse(
        (REPOSITORY_ROOT / "helpers/trace_middleware.py").read_text(encoding="utf-8")
    )
    trace_tree = ast.parse(
        (REPOSITORY_ROOT / "helpers/trace.py").read_text(encoding="utf-8")
    )
    assert (
        _function_return_strings(middleware_tree, "_command_event_name")
        <= _KNOWN_EVENT_LABELS
    )
    assert _function_return_strings(trace_tree, "_actor_type") <= _KNOWN_ACTOR_LABELS
    assert {
        "tg.callback",
        "tg.message",
        "trace",
        "unknown",
        "zoom.webhook",
    } <= _KNOWN_SOURCE_LABELS


def test_atomic_report_write_fsyncs_file_and_directory(tmp_path, monkeypatch):
    path = tmp_path / "report.md"
    fsync_calls: list[int] = []
    monkeypatch.setattr(report_io.os, "fsync", fsync_calls.append)

    atomic_write_text(path, "new report\n")

    assert path.read_text(encoding="utf-8") == "new report\n"
    assert len(fsync_calls) == 2


def test_atomic_report_write_keeps_old_target_if_flush_fails(tmp_path, monkeypatch):
    path = tmp_path / "report.md"
    path.write_text("old report\n", encoding="utf-8")

    def fail_fsync(_file_descriptor):
        raise OSError("synthetic flush failure")

    monkeypatch.setattr(report_io.os, "fsync", fail_fsync)

    with pytest.raises(AtomicReportWriteError, match="durably replace"):
        atomic_write_text(path, "new report\n")

    assert path.read_text(encoding="utf-8") == "old report\n"
    assert list(tmp_path.iterdir()) == [path]


def test_workload_validate_requires_both_report_members_and_rejects_stale(
    tmp_path, monkeypatch
):
    source = tmp_path / "events.jsonl"
    json_report = tmp_path / "workload-profile.json"
    markdown_report = tmp_path / "workload-profile.md"
    source.write_text(
        _line(
            ts="2026-03-20T10:00:00.000",
            event="update.message.received",
            source="tg.message",
            actor_type="student",
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(workload_profile, "JSON_REPORT", json_report)
    monkeypatch.setattr(workload_profile, "MARKDOWN_REPORT", markdown_report)
    workload_profile.write_reports((source,))

    for path in (json_report, markdown_report):
        expected = path.read_text(encoding="utf-8")
        path.unlink()
        with pytest.raises(WorkloadProfileError, match="workload-profile-update"):
            workload_profile.validate_reports((source,))
        path.write_text(expected, encoding="utf-8")
        path.write_text("stale\n", encoding="utf-8")
        with pytest.raises(WorkloadProfileError, match="workload-profile-update"):
            workload_profile.validate_reports((source,))
        path.write_text(expected, encoding="utf-8")
