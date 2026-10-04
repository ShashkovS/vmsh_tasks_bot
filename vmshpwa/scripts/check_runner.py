"""One measured, sequential fast/release gate without duplicate suites.

Fast uses Chromium; release preserves three engines. Every selected test runs
again; only build, schema/seed and compiler/linter work is cached. See
testing-strategy.md and pwa_tests/reports/check-optimization-20261003/README.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from vmshpwa.scripts.check_toolchain import frontend_environment
from vmshpwa.scripts.e2e_runner import E2eSuiteAlreadyRunning, exclusive_e2e_run

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "vmshpwa"
REPORTS = ROOT / ".runtime/vmshpwa/checks"


def source_digest() -> str:
    """Describe tested code, including dirty/untracked files, without secrets."""

    paths = (
        subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    digest = hashlib.sha256()
    suffixes = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".mjs",
        ".json",
        ".yaml",
        ".yml",
        ".sql",
        ".po",
        ".css",
        ".tex",
        ".html",
        ".svg",
        ".png",
        ".webp",
        ".toml",
        ".ini",
        ".cfg",
        ".sh",
    }
    for name in sorted(set(paths)):
        # Test reports are outputs, not source inputs. Golden fixtures and
        # Playwright screenshot baselines remain covered outside this folder.
        if name.startswith("pwa_tests/reports/"):
            continue
        path = ROOT / name
        if (
            name
            and path.is_file()
            and (path.suffix in suffixes or path.name in {"Makefile", "uv.lock"})
        ):
            digest.update(name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def lint_program_digest(workspace: Path) -> str:
    """Typed ESLint caches must also invalidate when a dependency's type changes."""

    digest = hashlib.sha256()
    for root, directories, files in os.walk(workspace):
        directories[:] = sorted(
            name
            for name in directories
            if name
            not in {
                "node_modules",
                "dist",
                "dev-dist",
                "test-results",
                "playwright-report",
                "storybook-static",
                "__pycache__",
            }
        )
        for name in sorted(files):
            path = Path(root) / name
            if path.suffix in {".ts", ".tsx", ".js", ".mjs", ".json", ".yaml"}:
                digest.update(str(path.relative_to(workspace)).encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


def steps(
    profile: str, modes: list[str], workers: int, report: Path
) -> list[tuple[str, list[str], Path]]:
    uv = ["uv", "run", "--frozen", "--no-sync"]
    e2e = [
        *uv,
        "python",
        "-m",
        "vmshpwa.scripts.e2e_runner",
        "--browser",
        "chromium" if profile == "fast" else "all",
        "--report",
        str(report / "e2e.json"),
    ]
    for mode in modes:
        e2e.extend(["--mode", mode])
    lint_cache = REPORTS / "lint" / lint_program_digest(WORKSPACE)
    return [
        ("python-dependencies", ["uv", "sync", "--frozen", "--check"], ROOT),
        ("format", ["pnpm", "format:check"], WORKSPACE),
        ("types", ["pnpm", "typecheck"], WORKSPACE),
        (
            "lint-js",
            [
                "pnpm",
                "exec",
                "eslint",
                ".",
                "--max-warnings=0",
                "--cache",
                "--cache-strategy",
                "content",
                "--cache-location",
                str(lint_cache),
            ],
            WORKSPACE,
        ),
        ("lint-css", ["pnpm", "lint:css"], WORKSPACE),
        ("i18n-frontend", ["pnpm", "i18n:check"], WORKSPACE),
        (
            "i18n-backend",
            [*uv, "python", "-m", "vmshpwa.scripts.backend_i18n", "check"],
            ROOT,
        ),
        (
            "python",
            [
                *uv,
                "pytest",
                "-q",
                f"-n{workers}",
                "--durations=20",
                "tests",
                "pwa_tests",
            ],
            ROOT,
        ),
        ("frontend", ["pnpm", "test"], WORKSPACE),
        ("storybook", ["pnpm", "storybook:test"], WORKSPACE),
        ("e2e", e2e, ROOT),
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("fast", "release"), default="fast")
    parser.add_argument(
        "--e2e-mode",
        action="append",
        help="Repeat for compatible feature scenarios; default is the complete suite",
    )
    parser.add_argument("--python-workers", type=int, default=4)
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args(argv)
    if args.python_workers < 1:
        parser.error("--python-workers must be positive")
    started = time.monotonic()
    report_dir = args.report_dir or REPORTS / datetime.now(UTC).strftime(
        "%Y%m%dT%H%M%S.%fZ"
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "profile": args.profile,
        "modes": args.e2e_mode or ["all"],
        "started_at": datetime.now(UTC).isoformat(),
        "steps": [],
        "exit_code": None,
    }
    result = 1
    try:
        with exclusive_e2e_run(REPORTS / "pipeline.lock"):
            environment = frontend_environment(
                WORKSPACE,
                {
                    **os.environ,
                    "CI": "true",
                    "UV_CACHE_DIR": str(ROOT / ".runtime/uv-cache"),
                    "PROD": "false",
                },
            )
            environment.update(
                VMSH_RUNTIME_PROFILE="pwa-e2e",
                VMSH_INSTANCE="e2e-pytest",
                VMSH_DB_FILENAME="db/vmshpwa_e2e.sqlite3",
                VMSH_ANALYTICS_DB_FILENAME=".runtime/vmshpwa/e2e/analytics.sqlite3",
                VMSH_MEDIA_ROOT=".runtime/vmshpwa/e2e-pytest",
                VMSH_NATS_SERVER="",
                VMSH_NATS_TOPIC_PREFIX="vmshpwa_e2e_pytest",
                VMSH_PWA_PROTOTYPE="true",
            )
            record["revision"] = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip()
            record["source_digest"] = source_digest()
            for name, command, cwd in steps(
                args.profile, args.e2e_mode or ["all"], args.python_workers, report_dir
            ):
                print(
                    f"Check {name}: starting (log: {report_dir / (name + '.log')})",
                    flush=True,
                )
                phase = time.monotonic()
                with (report_dir / f"{name}.log").open("w") as log:
                    result = subprocess.run(
                        command,
                        cwd=cwd,
                        env=environment,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        check=False,
                    ).returncode
                entry = {
                    "name": name,
                    "command": command,
                    "seconds": round(time.monotonic() - phase, 3),
                    "exit_code": result,
                }
                record["steps"].append(entry)
                print(
                    f"Check {name}: {'PASS' if result == 0 else 'FAIL'} in {entry['seconds']} s",
                    flush=True,
                )
                if result:
                    print((report_dir / f"{name}.log").read_text()[-6000:], flush=True)
                    break
            record["source_changed"] = record["source_digest"] != source_digest()
            if record["source_changed"]:
                print(
                    "Source changed during checks; this run is not a release receipt",
                    flush=True,
                )
                result = 75
    except E2eSuiteAlreadyRunning as error:
        print(error, flush=True)
        result = 73
    finally:
        record.update(seconds=round(time.monotonic() - started, 3), exit_code=result)
        (report_dir / "summary.json").write_text(json.dumps(record, indent=2) + "\n")
        print(f"Check report: {report_dir / 'summary.json'}", flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
