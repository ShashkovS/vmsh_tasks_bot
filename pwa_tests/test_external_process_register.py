from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REGISTER_PATH = (
    REPOSITORY_ROOT / "pwa_tests" / "fixtures" / "external-process-register.v1.json"
)
DOCUMENT_PATH = (
    REPOSITORY_ROOT
    / "vmshpwa"
    / "dev"
    / "development-plan"
    / "21-external-process-register.md"
)
RELATED_DOCUMENT_PATHS = (
    DOCUMENT_PATH,
    DOCUMENT_PATH.with_name("16-external-artifacts.md"),
    DOCUMENT_PATH.with_name("README.md"),
)

REGISTER_REQUIRED_FIELDS = {
    "schemaVersion",
    "registerId",
    "asOf",
    "language",
    "scope",
    "classifications",
    "externalSystems",
    "processes",
    "runbooks",
    "artifacts",
    "knownGaps",
    "transitionStates",
    "knownExternalDependencies",
}
SCOPE_REQUIRED_FIELDS = {
    "description",
    "privacyRule",
    "operationalRule",
    "evidencePaths",
}
SYSTEM_REQUIRED_FIELDS = {"id", "title", "credentialClass", "dataClasses"}
PROCESS_REQUIRED_FIELDS = {
    "id",
    "title",
    "classification",
    "owner",
    "trigger",
    "schedule",
    "inputs",
    "outputs",
    "sideEffects",
    "externalSystems",
    "credentialClasses",
    "rerunPolicy",
    "failureDetection",
    "recovery",
    "sourcePaths",
    "artifactIds",
    "invocation",
    "upstreamProcessIds",
    "transitionState",
    "target",
}
TARGET_REQUIRED_FIELDS = {"phase", "decision", "cutoverGate"}
ARTIFACT_REQUIRED_FIELDS = {
    "id",
    "path",
    "kind",
    "classification",
    "processIds",
    "targetPhase",
}
RUNBOOK_REQUIRED_FIELDS = {"id", "title", "status", "sourcePaths", "steps"}
KNOWN_GAP_REQUIRED_FIELDS = {"id", "description", "impact", "questionRef"}
EXTERNAL_DEPENDENCY_REQUIRED_FIELDS = {
    "id",
    "locator",
    "status",
    "requiredByProcessIds",
    "evidencePaths",
    "questionRef",
}


def _assert_unique(values: list[str], label: str) -> None:
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    assert not duplicates, f"duplicate {label}: {duplicates}"


def _markdown_anchors(document_path: Path) -> set[str]:
    anchors: set[str] = set()
    occurrences: Counter[str] = Counter()
    for line in document_path.read_text(encoding="utf-8").splitlines():
        heading = re.fullmatch(r"#{1,6}\s+(.+?)\s*#*", line)
        if heading is None:
            continue
        title = heading.group(1).strip().lower()
        # These repository references follow GitHub-style heading anchors. The
        # implementation-question headings intentionally avoid punctuation-heavy
        # labels, so preserving Unicode word characters is both deterministic and
        # sufficient for validating the committed references.
        slug = re.sub(r"[^\w\- ]", "", title, flags=re.UNICODE)
        slug = re.sub(r"\s+", "-", slug).strip("-")
        suffix = occurrences[slug]
        occurrences[slug] += 1
        anchors.add(slug if suffix == 0 else f"{slug}-{suffix}")
    return anchors


def _assert_question_ref_resolves(value: str) -> None:
    relative_path, separator, fragment = value.partition("#")
    assert separator and relative_path and fragment, value
    document_path = DOCUMENT_PATH.parent / relative_path
    assert document_path.exists(), value
    assert fragment in _markdown_anchors(document_path), value


def _object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        assert key not in result, f"duplicate JSON object key: {key}"
        result[key] = value
    return result


def _load_register() -> dict:
    return json.loads(
        REGISTER_PATH.read_text(encoding="utf-8"),
        object_pairs_hook=_object_without_duplicate_keys,
    )


def _assert_relative_existing_path(value: str) -> None:
    path = Path(value)
    assert not path.is_absolute(), value
    assert ".." not in path.parts, value
    resolved = (REPOSITORY_ROOT / path).resolve()
    assert resolved.is_relative_to(REPOSITORY_ROOT), value
    assert resolved.exists(), value


def _external_inventory_paths() -> set[str]:
    root = REPOSITORY_ROOT / "_external_pipelines"
    direct_artifacts = {
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in root.iterdir()
        if path.is_file() and path.name != ".DS_Store"
    }
    # Media files belong to the private Telegram corpus as one logical artifact;
    # listing each filename would expose and churn historical message metadata.
    direct_artifacts.add("_external_pipelines/ChatExport_2026-07-25/result.json")
    return direct_artifacts


def test_register_has_complete_typed_process_records_and_valid_links():
    register = _load_register()

    assert set(register) == REGISTER_REQUIRED_FIELDS
    assert register["schemaVersion"] == 1
    assert register["registerId"] and register["asOf"] and register["language"]
    assert set(register["scope"]) == SCOPE_REQUIRED_FIELDS
    assert all(register["scope"][field] for field in SCOPE_REQUIRED_FIELDS)
    _assert_unique(register["classifications"], "classification")
    classifications = set(register["classifications"])
    assert classifications == {
        "active_external",
        "active_automated",
        "manual_digital",
        "manual_physical",
        "legacy_reference",
    }

    assert register["transitionStates"] == [
        "legacy_bridge",
        "v1_cutover",
        "later_internalization",
    ]
    _assert_unique(register["transitionStates"], "transition state")
    transition_states = set(register["transitionStates"])

    system_ids = [system["id"] for system in register["externalSystems"]]
    process_ids = [process["id"] for process in register["processes"]]
    artifact_ids = [artifact["id"] for artifact in register["artifacts"]]
    _assert_unique(system_ids, "external system id")
    _assert_unique(process_ids, "process id")
    _assert_unique(artifact_ids, "artifact id")
    systems = {system["id"]: system for system in register["externalSystems"]}
    processes = {process["id"]: process for process in register["processes"]}
    artifacts = {artifact["id"]: artifact for artifact in register["artifacts"]}

    for source_path in register["scope"]["evidencePaths"]:
        _assert_relative_existing_path(source_path)

    for system in systems.values():
        assert set(system) == SYSTEM_REQUIRED_FIELDS, system["id"]
        assert system["title"] and system["credentialClass"]
        assert system["dataClasses"]
        _assert_unique(system["dataClasses"], f"{system['id']} data class")

    for process in processes.values():
        assert set(process) == PROCESS_REQUIRED_FIELDS, process["id"]
        assert process["classification"] in classifications
        for field in PROCESS_REQUIRED_FIELDS - {"artifactIds", "upstreamProcessIds"}:
            assert process[field], f"{process['id']}.{field}"
        assert process["transitionState"] in transition_states
        assert set(process["target"]) == TARGET_REQUIRED_FIELDS
        assert all(process["target"].values())
        assert set(process["externalSystems"]).issubset(systems)
        assert set(process["artifactIds"]).issubset(artifacts)
        assert set(process["upstreamProcessIds"]).issubset(processes)
        assert process["id"] not in process["upstreamProcessIds"]
        _assert_unique(process["upstreamProcessIds"], f"{process['id']} upstream")
        _assert_unique(process["artifactIds"], f"{process['id']} artifact link")
        _assert_unique(process["sourcePaths"], f"{process['id']} source path")
        for list_field in (
            "inputs",
            "outputs",
            "sideEffects",
            "externalSystems",
            "credentialClasses",
        ):
            assert process[list_field], f"{process['id']}.{list_field}"
            assert all(
                isinstance(item, str) and item for item in process[list_field]
            ), f"{process['id']}.{list_field}"
            _assert_unique(process[list_field], f"{process['id']} {list_field}")
        for source_path in process["sourcePaths"]:
            _assert_relative_existing_path(source_path)

    unresolved = set(processes)
    resolved: set[str] = set()
    while unresolved:
        ready = {
            process_id
            for process_id in unresolved
            if set(processes[process_id]["upstreamProcessIds"]).issubset(resolved)
        }
        assert ready, f"cyclic upstreamProcessIds: {sorted(unresolved)}"
        unresolved -= ready
        resolved |= ready

    for artifact in artifacts.values():
        assert set(artifact) == ARTIFACT_REQUIRED_FIELDS, artifact["id"]
        assert artifact["classification"] in classifications
        assert artifact["kind"] and artifact["targetPhase"]
        assert artifact["processIds"]
        assert set(artifact["processIds"]).issubset(processes)
        _assert_unique(artifact["processIds"], f"{artifact['id']} process link")
        _assert_relative_existing_path(artifact["path"])

    for process in processes.values():
        for artifact_id in process["artifactIds"]:
            assert process["id"] in artifacts[artifact_id]["processIds"]
    for artifact in artifacts.values():
        for process_id in artifact["processIds"]:
            assert artifact["id"] in processes[process_id]["artifactIds"]

    dependency_ids = [
        dependency["id"] for dependency in register["knownExternalDependencies"]
    ]
    _assert_unique(dependency_ids, "external dependency id")
    for dependency in register["knownExternalDependencies"]:
        assert set(dependency) == EXTERNAL_DEPENDENCY_REQUIRED_FIELDS
        assert dependency["locator"] and dependency["status"]
        assert dependency["requiredByProcessIds"]
        assert set(dependency["requiredByProcessIds"]).issubset(processes)
        _assert_unique(
            dependency["requiredByProcessIds"],
            f"{dependency['id']} required process",
        )
        assert dependency["evidencePaths"]
        _assert_unique(dependency["evidencePaths"], f"{dependency['id']} evidence")
        for evidence_path in dependency["evidencePaths"]:
            _assert_relative_existing_path(evidence_path)
        _assert_question_ref_resolves(dependency["questionRef"])

    gap_ids = [gap["id"] for gap in register["knownGaps"]]
    _assert_unique(gap_ids, "known gap id")
    for gap in register["knownGaps"]:
        assert set(gap) == KNOWN_GAP_REQUIRED_FIELDS, gap["id"]
        assert gap["description"] and gap["impact"]
        if gap["questionRef"] is not None:
            _assert_question_ref_resolves(gap["questionRef"])


def test_every_external_script_or_reference_artifact_is_classified_once():
    register = _load_register()
    registered_paths = [artifact["path"] for artifact in register["artifacts"]]

    _assert_unique(registered_paths, "external artifact path")
    assert set(registered_paths) == _external_inventory_paths()


def test_runbooks_are_ordered_and_reference_registered_processes():
    register = _load_register()
    process_ids = {process["id"] for process in register["processes"]}
    runbook_ids = [runbook["id"] for runbook in register["runbooks"]]
    _assert_unique(runbook_ids, "runbook id")

    for runbook in register["runbooks"]:
        assert set(runbook) == RUNBOOK_REQUIRED_FIELDS, runbook["id"]
        assert runbook["title"]
        assert runbook["status"]
        assert runbook["steps"]
        _assert_unique(runbook["sourcePaths"], f"{runbook['id']} source path")
        assert [step["order"] for step in runbook["steps"]] == list(
            range(1, len(runbook["steps"]) + 1)
        )
        for source_path in runbook["sourcePaths"]:
            _assert_relative_existing_path(source_path)
        for step in runbook["steps"]:
            assert set(step) == {"order", "window", "processId", "instruction"}
            assert step["processId"] in process_ids
            assert step["window"] and step["instruction"]


def test_readable_register_covers_every_machine_record():
    register = _load_register()
    document = DOCUMENT_PATH.read_text(encoding="utf-8")

    for process in register["processes"]:
        assert f"`{process['id']}`" in document
    for artifact in register["artifacts"]:
        assert f"`{artifact['id']}`" in document
    for runbook in register["runbooks"]:
        assert f"`{runbook['id']}`" in document


def test_register_documentation_local_links_resolve():
    for document_path in RELATED_DOCUMENT_PATHS:
        document = document_path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^]]*]\(([^)]+)\)", document):
            if target.startswith(("#", "http://", "https://")):
                continue
            relative_path = target.partition("#")[0]
            assert (document_path.parent / relative_path).resolve().exists(), (
                document_path,
                target,
            )


def test_register_contains_no_secret_values_or_copied_log_payloads():
    rendered = REGISTER_PATH.read_text(encoding="utf-8")

    assert "events.jsonl" not in rendered
    assert "selected.jsonl" not in rendered
    assert '"messages"' not in rendered
    assert not re.search(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", rendered)
    assert not re.search(r"\b[1-9][0-9]{4,15}:[A-Za-z0-9_-]{20,128}\b", rendered)
    assert not re.search(r"https://api\.telegram\.org/bot[^/\s]+", rendered)
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", rendered)
    assert not re.search(r'"chat_id"\s*:', rendered, flags=re.IGNORECASE)


def test_unsafe_restore_window_and_sensitive_mailing_input_are_explicit():
    register = _load_register()
    processes = {process["id"]: process for process in register["processes"]}
    dependencies = {
        dependency["id"]: dependency
        for dependency in register["knownExternalDependencies"]
    }

    mirror = processes["production-db-mirror"]
    mirror_text = " ".join([*mirror["sideEffects"], mirror["recovery"]]).lower()
    assert "неатомар" in mirror_text
    assert ".temp" in mirror_text
    assert "частич" in mirror_text
    assert "atomic" in mirror["target"]["cutoverGate"].lower()

    workbook = dependencies["registration-credentials-workbook"]
    assert workbook["requiredByProcessIds"] == ["post-review-mailing"]
    assert workbook["evidencePaths"] == ["_external_pipelines/a22_create_mails.py"]
    assert "absent" in workbook["status"]
    mailing_inputs = " ".join(processes["post-review-mailing"]["inputs"]).lower()
    for required_label in ("заявки и пароли", "password", "email"):
        assert required_label in mailing_inputs
