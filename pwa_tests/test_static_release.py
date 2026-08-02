from __future__ import annotations

import json
from pathlib import Path

import pytest

from vmshpwa.scripts import static_release


RECORDED_AT = "2026-07-30T18:00:00Z"


def _bundles(root: Path, marker: str) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    for app_name in ("student", "family", "staff"):
        source = root / app_name
        source.mkdir(parents=True)
        (source / "index.html").write_text(marker, encoding="utf-8")
        if app_name != "staff":
            (source / "manifest.webmanifest").write_text("{}", encoding="utf-8")
            (source / "sw.js").write_text("// worker", encoding="utf-8")
        sources[app_name] = source
    return sources


@pytest.fixture
def release_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "releases"
    monkeypatch.setattr(static_release, "RELEASE_ROOT", root)
    return root


def test_packages_and_rolls_back_complete_frontend_set(
    tmp_path: Path, release_root: Path
) -> None:
    sources = _bundles(tmp_path / "bundles", "first")
    first = static_release.package_release("revision-a", RECORDED_AT, sources=sources)
    for source in sources.values():
        (source / "index.html").write_text("second", encoding="utf-8")
    second = static_release.package_release("revision-b", RECORDED_AT, sources=sources)

    verified = static_release.verify_release("revision-a", RECORDED_AT)
    static_release.activate_release("revision-a", RECORDED_AT)
    activated = static_release.activate_release("revision-b", RECORDED_AT)
    rolled_back = static_release.activate_release(
        "revision-a", RECORDED_AT, action="rollback"
    )

    assert (
        first["applications"]["student"]["sha256"]
        != second["applications"]["student"]["sha256"]
    )
    assert verified["operation"] == "static-release-verify"
    assert verified["applications"] == first["applications"]
    assert activated["previousReleaseId"] == "revision-a"
    assert rolled_back["previousReleaseId"] == "revision-b"
    assert release_root.joinpath("current").readlink().as_posix() == "revision-a"
    assert release_root.joinpath("current/student/index.html").read_text() == "first"
    assert (
        json.loads(release_root.joinpath("revision-a/release.json").read_text())[
            "releaseId"
        ]
        == "revision-a"
    )


def test_package_rejects_incomplete_or_existing_release(
    tmp_path: Path, release_root: Path
) -> None:
    sources = _bundles(tmp_path / "bundles", "ready")
    sources["student"].joinpath("sw.js").unlink()
    with pytest.raises(ValueError, match="student/sw.js"):
        static_release.package_release("revision-a", RECORDED_AT, sources=sources)

    sources["student"].joinpath("sw.js").write_text("// worker")
    static_release.package_release("revision-a", RECORDED_AT, sources=sources)
    with pytest.raises(ValueError, match="already exists"):
        static_release.package_release("revision-a", RECORDED_AT, sources=sources)


def test_activation_refuses_missing_release_and_non_symlink_current(
    release_root: Path,
) -> None:
    with pytest.raises(ValueError, match="missing or incomplete"):
        static_release.activate_release("missing", RECORDED_AT)

    release_root.mkdir(parents=True)
    release_root.joinpath("current").mkdir()
    release_root.joinpath("revision-a").mkdir()
    release_root.joinpath("revision-a/release.json").write_text("{}")
    with pytest.raises(ValueError, match="not a symlink"):
        static_release.activate_release("revision-a", RECORDED_AT)


@pytest.mark.parametrize(
    ("tamper", "message"),
    (
        (
            lambda release: release.joinpath("student/index.html").write_text(
                "changed"
            ),
            "student",
        ),
        (lambda release: release.joinpath("family/sw.js").unlink(), "family/sw.js"),
        (
            lambda release: release.joinpath("extra.txt").write_text("unexpected"),
            "unexpected",
        ),
    ),
)
def test_verify_and_activation_reject_tampered_release(
    tmp_path: Path,
    release_root: Path,
    tamper,
    message: str,
) -> None:
    sources = _bundles(tmp_path / "bundles", "ready")
    static_release.package_release("revision-a", RECORDED_AT, sources=sources)
    tamper(release_root / "revision-a")

    with pytest.raises(ValueError, match=message):
        static_release.verify_release("revision-a", RECORDED_AT)
    with pytest.raises(ValueError, match=message):
        static_release.activate_release("revision-a", RECORDED_AT)
    assert not release_root.joinpath("current").exists()


def test_verify_rejects_malformed_or_wrong_manifest(
    tmp_path: Path, release_root: Path
) -> None:
    sources = _bundles(tmp_path / "bundles", "ready")
    static_release.package_release("revision-a", RECORDED_AT, sources=sources)
    manifest_path = release_root / "revision-a/release.json"

    manifest_path.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest is unreadable"):
        static_release.verify_release("revision-a", RECORDED_AT)

    manifest_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "releaseId": "revision-b",
                "applications": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="identity"):
        static_release.verify_release("revision-a", RECORDED_AT)


def test_verify_rejects_symlinked_bundle(tmp_path: Path, release_root: Path) -> None:
    sources = _bundles(tmp_path / "bundles", "ready")
    static_release.package_release("revision-a", RECORDED_AT, sources=sources)
    student = release_root / "revision-a/student"
    moved_student = tmp_path / "moved-student"
    student.rename(moved_student)
    student.symlink_to(moved_student, target_is_directory=True)

    with pytest.raises(ValueError, match="student"):
        static_release.verify_release("revision-a", RECORDED_AT)


@pytest.mark.parametrize("release_id", ("../escape", "UPPER", "a/b", ""))
def test_release_id_is_a_single_safe_lowercase_label(
    release_root: Path, release_id: str
) -> None:
    with pytest.raises(ValueError, match="lowercase revision label"):
        static_release.activate_release(release_id, RECORDED_AT)
