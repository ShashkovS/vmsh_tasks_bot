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
import json
import os
import subprocess
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from vmshpwa.scripts.check_toolchain import frontend_environment
from vmshpwa.scripts.e2e_build_cache import (
    build_input_digest,
    cached_build_is_current,
    record_build,
)

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
    "VMSH_FRONTEND_BUILD_PROFILE": "verification",
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
            # P8 final regression: these destructive fixtures share lesson IDs
            # with content/live-marking. Give them fresh seeded SQLite phases.
            (
                *playwright,
                r"e2e/(?!figure-layout|statistics-recalculation|statistics-reports).*\.spec\.ts",
                "--grep-invert",
                "@visual",
            ),
            (*playwright, "e2e/figure-layout.spec.ts"),
            (*playwright, "--config", "playwright.statistics.config.ts"),
            (*playwright, "--grep", "@visual"),
        )
    if mode == "authentication":
        playwright.append("e2e/authentication.spec.ts")
    elif mode == "statistics":
        playwright.extend(["--config", "playwright.statistics.config.ts"])
    elif mode == "figure-layout":
        playwright.extend(
            [
                "e2e/figure-layout.spec.ts",
                "e2e/whiteboard-export.spec.ts",
                "e2e/worksheet-print.spec.ts",
            ]
        )
    elif mode == "offline-current":
        playwright.extend(
            ["e2e/offline-current-lessons.spec.ts", "e2e/content-publication.spec.ts"]
        )
    elif mode == "problem-release":
        playwright.extend(["e2e/problem-release.spec.ts", "--retries", "0"])
    elif mode == "content":
        playwright.append("e2e/content-publication.spec.ts")
    elif mode == "family":
        playwright.append("e2e/family-context.spec.ts")
    elif mode == "i18n":
        playwright.append("e2e/i18n.spec.ts")
    elif mode == "submissions":
        playwright.append("e2e/test-submission.spec.ts")
    elif mode == "review":
        playwright.append("e2e/review-workspace.spec.ts")
    elif mode == "support":
        playwright.append("e2e/support-dialogue.spec.ts")
    elif mode == "portal-release":
        # production-rollout-checklist.md: destructive fixture families receive
        # fresh SQLite phases, just like the existing full release suite.
        phases = (
            (
                "e2e/authentication.spec.ts",
                "e2e/family-context.spec.ts",
                "e2e/i18n.spec.ts",
            ),
            ("e2e/branding.spec.ts",),
            ("e2e/course-attendance.spec.ts",),
            ("e2e/content-publication.spec.ts",),
            ("e2e/smooth-redeploy.spec.ts",),
        )
        return (
            ("pnpm", "build"),
            *((*playwright, *phase, "--grep-invert", "@visual") for phase in phases),
        )
    elif mode == "course-attendance":
        playwright.append("e2e/course-attendance.spec.ts")
    elif mode == "classrooms":
        playwright.append("e2e/classroom-catalog.spec.ts")
    elif mode == "organizers":
        playwright.append("e2e/organizer-questions.spec.ts")
    elif mode == "student-results":
        playwright.append("e2e/student-results.spec.ts")
    elif mode == "oral":
        playwright.extend(["e2e/oral-admission.spec.ts", "e2e/live-marking.spec.ts"])
    elif mode == "oral-windows":
        playwright.append("e2e/oral-windows-weekly.spec.ts")
    elif mode == "redeploy":
        playwright.append("e2e/smooth-redeploy.spec.ts")
    elif mode == "live-marking":
        playwright.extend(
            ["e2e/live-marking.spec.ts", "e2e/live-marking-confirmation.spec.ts"]
        )
    elif mode == "news":
        playwright.append("e2e/news-notifications.spec.ts")
    elif mode == "rich-files":
        playwright.append("e2e/rich-file-attachments.spec.ts")
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


def commands_for_request(
    modes: Sequence[str], browser: str = "all"
) -> tuple[tuple[str, ...], ...]:
    """Batch compatible focused specs; preserve destructive fresh-seed phases.

    testing-strategy.md: each batch has one real backend/gateway. Figure,
    report, visual and explicitly destructive fixtures still get fresh state.
    """

    destructive = {
        "all",
        "portal-release",
        "figure-layout",
        "statistics",
        "visual",
        "visual-update",
        "student-results",
        "organizers",
        "oral",
        "oral-windows",
        "live-marking",
        "problem-release",
    }
    phases: list[tuple[str, ...]] = []
    selectors: list[str] = []
    playwright = ("pnpm", "exec", "playwright", "test")
    if len(set(modes)) > 1 and set(modes) & {"all", "nonvisual", "portal-release"}:
        raise ValueError(
            "A broad E2E mode already includes focused specs; run it separately"
        )

    def flush() -> None:
        if selectors:
            phases.append((*playwright, *dict.fromkeys(selectors)))
            selectors.clear()

    for mode in dict.fromkeys(modes):
        commands = commands_for_mode(mode)[1:]
        arguments = commands[0][4:]
        if (
            mode not in destructive
            and len(commands) == 1
            and arguments
            and all(
                arg.startswith("e2e/") and arg.endswith(".spec.ts") for arg in arguments
            )
        ):
            selectors.extend(arguments)
        else:
            flush()
            phases.extend(commands)
    flush()
    browser_flags = () if browser == "all" else ("--project", browser)
    return (
        ("pnpm", "build"),
        *(
            tuple(phase)
            + browser_flags
            + (() if "--retries" in phase else ("--retries", "0"))
            for phase in phases
        ),
    )


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
    reuse_build: bool = False,
    force_build: bool = False,
    timings: list[dict] | None = None,
) -> int:
    subprocess_environment = sanitized_e2e_environment(environment)
    for index, command in enumerate(commands):
        started = time.monotonic()
        is_build = tuple(command) == ("pnpm", "build")
        if (
            is_build
            and reuse_build
            and not force_build
            and cached_build_is_current(workspace, subprocess_environment)
        ):
            print(
                "E2E build: cache hit (source, environment and all artifact bytes match)",
                flush=True,
            )
            if timings is not None:
                timings.append(
                    {
                        "command": list(command),
                        "seconds": round(time.monotonic() - started, 3),
                        "cache_hit": True,
                        "exit_code": 0,
                    }
                )
            continue
        build_key = (
            build_input_digest(workspace, subprocess_environment)
            if is_build and reuse_build
            else None
        )
        if reset_database_between_commands and index > 0:
            reset_e2e_database()
        result = subprocess.run(
            command,
            cwd=workspace,
            env=subprocess_environment,
            check=False,
        )
        if timings is not None:
            entry = {
                "command": list(command),
                "seconds": round(time.monotonic() - started, 3),
                "cache_hit": False,
                "exit_code": result.returncode,
            }
            preparation = (
                workspace.parent / ".runtime/vmshpwa/e2e-cache/preparation-latest.json"
            )
            if not is_build and result.returncode == 0 and preparation.is_file():
                entry["preparation"] = json.loads(preparation.read_text())
            timings.append(entry)
        if result.returncode != 0:
            return result.returncode
        if is_build and reuse_build:
            if build_key != build_input_digest(workspace, subprocess_environment):
                raise RuntimeError("Frontend inputs changed during the build; rerun")
            record_build(workspace, subprocess_environment)
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        action="append",
        choices=(
            "all",
            "authentication",
            "classrooms",
            "course-attendance",
            "portal-release",
            "content",
            "problem-release",
            "offline-current",
            "figure-layout",
            "statistics",
            "family",
            "i18n",
            "nonvisual",
            "news",
            "rich-files",
            "oral",
            "oral-windows",
            "redeploy",
            "live-marking",
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
    )
    parser.add_argument(
        "--browser", choices=("chromium", "webkit", "firefox", "all"), default="all"
    )
    parser.add_argument(
        "--fresh-build",
        action="store_true",
        help="Rebuild even when verified artifacts match",
    )
    parser.add_argument(
        "--fresh-seed",
        action="store_true",
        help="Recreate the seed snapshot from repository fixtures",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPOSITORY_ROOT / ".runtime/vmshpwa/checks/e2e-latest.json",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    modes = args.mode or ["all"]
    started = time.monotonic()
    timings: list[dict] = []
    try:
        with exclusive_e2e_run():
            environment = frontend_environment(WORKSPACE, dict(os.environ))
            environment["VMSH_E2E_FRESH_SEED"] = "1" if args.fresh_seed else "0"
            environment["VMSH_E2E_SUPPORT_NAVIGATION"] = (
                "1" if "support" in modes else "0"
            )
            result = run_commands(
                commands_for_request(modes, args.browser),
                environment=environment,
                reuse_build=True,
                force_build=args.fresh_build,
                timings=timings,
            )
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(
                json.dumps(
                    {
                        "modes": modes,
                        "browser": args.browser,
                        "seconds": round(time.monotonic() - started, 3),
                        "exit_code": result,
                        "phases": timings,
                    },
                    indent=2,
                )
                + "\n"
            )
            return result
    except E2eSuiteAlreadyRunning as error:
        print(error)
        return 73


if __name__ == "__main__":
    raise SystemExit(main())
