"""Run the production E2E suite under one cross-process workspace lock.

Build output, Playwright ports and the seeded SQLite are intentionally shared
by one suite invocation. A kernel lock makes accidental concurrent runs fail
before either process rebuilds ``dist`` or seeds the database; human/agent dev
profiles remain independent and are not covered by this lock. See Phase 0 in
``vmshpwa/dev/development-plan/04-phase-0-baseline.md``.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = REPOSITORY_ROOT / "vmshpwa"
DEFAULT_LOCK_PATH = REPOSITORY_ROOT / ".runtime/vmshpwa/e2e-suite.lock"
E2E_API_ORIGIN = "http://127.0.0.1:8380"
E2E_DATABASE = REPOSITORY_ROOT / "db/vmshpwa_e2e.sqlite3"

# These are the complete browser-facing inputs currently consumed by the
# workspace. Values from a developer shell must not turn the hermetic E2E
# bundle into a Sentry client, enable a production media origin, or activate a
# prototype adapter. Removing every inherited ``VITE_*`` key first makes a
# future variable fail closed until it is reviewed and explicitly added here.
# See ``vmshpwa/docs/testing-strategy.md`` and the browser network guard in
# ``vmshpwa/e2e/fixtures.ts``.
E2E_BROWSER_BUILD_ENVIRONMENT = {
    "VITE_ENABLE_MSW": "false",
    "VITE_PROTOTYPE": "false",
    "VITE_PUBLIC_MEDIA_ORIGIN": "",
    "VITE_SENTRY_DSN": "",
    "VITE_SENTRY_RELEASE": "",
}
E2E_FRONTEND_TOOL_ENVIRONMENT = {
    "VMSH_API_ORIGIN": E2E_API_ORIGIN,
    "VMSH_PWA_DEV_SW": "0",
}


class E2eSuiteAlreadyRunning(RuntimeError):
    """Raised before any build/seed mutation when another suite owns the lock."""


@contextmanager
def exclusive_e2e_run(lock_path: Path = DEFAULT_LOCK_PATH) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            lock_file.seek(0)
            owner = lock_file.read().strip() or "owner metadata unavailable"
            raise E2eSuiteAlreadyRunning(
                f"Another vmshpwa E2E/visual run owns {lock_path}: {owner}"
            ) from error

        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(f"pid={os.getpid()} started={datetime.now(UTC).isoformat()}\n")
        lock_file.flush()
        os.fsync(lock_file.fileno())
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def commands_for_mode(mode: str) -> tuple[tuple[str, ...], ...]:
    playwright = ["pnpm", "exec", "playwright", "test"]
    if mode == "all":
        return (
            ("pnpm", "build"),
            (*playwright, "--grep-invert", "@visual"),
            (*playwright, "--grep", "@visual"),
        )
    if mode == "authentication":
        playwright.append("e2e/authentication.spec.ts")
    elif mode == "content":
        playwright.append("e2e/content-publication.spec.ts")
    elif mode == "family":
        playwright.append("e2e/family-context.spec.ts")
    elif mode == "submissions":
        playwright.append("e2e/test-submission.spec.ts")
    elif mode == "review":
        playwright.append("e2e/review-workspace.spec.ts")
    elif mode == "support":
        playwright.append("e2e/support-dialogue.spec.ts")
    elif mode == "classrooms":
        playwright.append("e2e/classroom-catalog.spec.ts")
    elif mode == "organizers":
        playwright.append("e2e/organizer-questions.spec.ts")
    elif mode == "student-results":
        playwright.append("e2e/student-results.spec.ts")
    elif mode == "oral":
        playwright.extend(["e2e/oral-admission.spec.ts", "e2e/live-marking.spec.ts"])
    elif mode == "news":
        playwright.append("e2e/news-notifications.spec.ts")
    elif mode == "runtime-isolation":
        playwright.append("e2e/runtime-isolation.spec.ts")
    elif mode == "realtime":
        playwright.extend(
            [
                "e2e/runtime-isolation.spec.ts",
                "--grep",
                "product realtime|current-session revoke",
            ]
        )
    elif mode == "nonvisual":
        playwright.extend(["--grep-invert", "@visual"])
    elif mode == "visual":
        playwright.extend(["--grep", "@visual"])
    elif mode == "visual-update":
        playwright.extend(["--grep", "@visual", "--update-snapshots"])
    else:
        raise ValueError(f"Unknown E2E mode: {mode}")
    return (("pnpm", "build"), tuple(playwright))


def reset_e2e_database() -> None:
    """Reset only the reproducible E2E SQLite database between suite phases."""

    paths = (
        E2E_DATABASE,
        E2E_DATABASE.with_name(f"{E2E_DATABASE.name}-shm"),
        E2E_DATABASE.with_name(f"{E2E_DATABASE.name}-wal"),
    )
    for path in paths:
        path.unlink(missing_ok=True)


def sanitized_e2e_environment(
    inherited: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return tool environment with an explicit browser-build allowlist.

    The E2E runner still needs ordinary process settings such as ``PATH``,
    locale and Playwright browser locations, so it cannot use a completely
    empty process environment. Browser-facing Vite keys are different: they
    are copied into production JavaScript and therefore use a deny-all,
    explicitly-safe replacement policy.
    """

    source = os.environ if inherited is None else inherited
    environment = {
        name: value
        for name, value in source.items()
        if not name.startswith("VITE_") and name not in E2E_FRONTEND_TOOL_ENVIRONMENT
    }
    environment.update(E2E_BROWSER_BUILD_ENVIRONMENT)
    environment.update(E2E_FRONTEND_TOOL_ENVIRONMENT)
    return environment


def run_commands(
    commands: Sequence[Sequence[str]],
    *,
    workspace: Path = WORKSPACE,
    environment: Mapping[str, str] | None = None,
    reset_database_between_commands: bool = False,
) -> int:
    subprocess_environment = sanitized_e2e_environment(environment)
    for index, command in enumerate(commands):
        if reset_database_between_commands and index > 0:
            reset_e2e_database()
        result = subprocess.run(
            command,
            cwd=workspace,
            env=subprocess_environment,
            check=False,
        )
        if result.returncode != 0:
            return result.returncode
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=(
            "all",
            "authentication",
            "classrooms",
            "content",
            "family",
            "nonvisual",
            "news",
            "oral",
            "student-results",
            "organizers",
            "runtime-isolation",
            "realtime",
            "review",
            "support",
            "submissions",
            "visual",
            "visual-update",
        ),
        default="all",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        with exclusive_e2e_run():
            return run_commands(
                commands_for_mode(args.mode),
                reset_database_between_commands=args.mode
                in {"all", "oral", "student-results", "organizers"},
            )
    except E2eSuiteAlreadyRunning as error:
        print(error)
        return 73


if __name__ == "__main__":
    raise SystemExit(main())
