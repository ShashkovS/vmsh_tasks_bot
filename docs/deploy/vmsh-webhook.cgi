#!/usr/bin/python3
"""Small GitHub webhook boundary for explicitly configured deploy scripts."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import yaml


CONFIG_PATH = Path("/web/vmsh_tasks_bot/deploy/config/webhook.yml")
SAFE_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"
DELIVERY_RE = re.compile(r"[A-Za-z0-9-]{1,100}")
USER_RE = re.compile(r"[a-z_][a-z0-9_-]{0,31}")


class WebhookError(Exception):
    def __init__(self, status: int, public_message: str, log_message: str | None = None):
        super().__init__(log_message or public_message)
        self.status = status
        self.public_message = public_message


def respond(status: int, message: str) -> None:
    reasons = {
        200: "OK",
        202: "Accepted",
        400: "Bad Request",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        413: "Payload Too Large",
        500: "Internal Server Error",
        503: "Service Unavailable",
    }
    print(f"Status: {status} {reasons.get(status, 'Error')}")
    print("Content-Type: text/plain; charset=utf-8")
    print("Cache-Control: no-store")
    print("X-Content-Type-Options: nosniff")
    print()
    print(message)


def secure_regular_file(path: Path, *, executable: bool = False) -> os.stat_result:
    try:
        details = path.stat()
    except OSError as error:
        raise WebhookError(500, "Webhook configuration is unavailable", str(error)) from error
    if not stat.S_ISREG(details.st_mode):
        raise WebhookError(500, "Webhook configuration is invalid", f"Not a file: {path}")
    if details.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise WebhookError(
            500,
            "Webhook configuration is unsafe",
            f"Group/world writable file rejected: {path}",
        )
    if executable and not os.access(path, os.X_OK):
        raise WebhookError(500, "Deploy command is unavailable", f"Not executable: {path}")
    return details


def load_config() -> dict[str, object]:
    secure_regular_file(CONFIG_PATH)
    try:
        document = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise WebhookError(500, "Webhook configuration is invalid", str(error)) from error
    if not isinstance(document, dict) or document.get("version") != 1:
        raise WebhookError(500, "Webhook configuration is invalid")
    return document


def setup_logging(config: dict[str, object]) -> None:
    configured = config.get("log_file")
    log_file = Path(configured) if isinstance(configured, str) else None
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file is not None:
        try:
            handlers.insert(0, logging.FileHandler(log_file, encoding="utf-8"))
        except OSError:
            pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def read_payload(maximum: int) -> bytes:
    raw_length = os.environ.get("CONTENT_LENGTH", "")
    try:
        length = int(raw_length)
    except ValueError as error:
        raise WebhookError(400, "Invalid Content-Length") from error
    if length <= 0:
        raise WebhookError(400, "Empty webhook payload")
    if length > maximum:
        raise WebhookError(413, "Webhook payload is too large")
    payload = sys.stdin.buffer.read(length)
    if len(payload) != length:
        raise WebhookError(400, "Incomplete webhook payload")
    return payload


def verify_signature(secret_file: Path, payload: bytes) -> None:
    secure_regular_file(secret_file)
    try:
        secret = secret_file.read_bytes().strip()
    except OSError as error:
        raise WebhookError(500, "Webhook secret is unavailable", str(error)) from error
    if len(secret) < 32:
        raise WebhookError(500, "Webhook secret is invalid")
    supplied = os.environ.get("HTTP_X_HUB_SIGNATURE_256", "")
    expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise WebhookError(403, "Invalid webhook signature")


def configured_project(
    config: dict[str, object], repository: str
) -> tuple[dict[str, object], dict[str, object]]:
    projects = config.get("projects")
    project = projects.get(repository) if isinstance(projects, dict) else None
    if not isinstance(project, dict):
        raise WebhookError(404, "Repository is not configured")
    refs = project.get("refs")
    if not isinstance(refs, dict):
        raise WebhookError(500, "Repository webhook configuration is invalid")
    return project, refs


def launch_deploy(target: dict[str, object], launch_log: Path) -> int:
    user = target.get("run_as")
    script_value = target.get("deploy_script")
    if not isinstance(user, str) or USER_RE.fullmatch(user) is None:
        raise WebhookError(500, "Deploy user is invalid")
    if not isinstance(script_value, str):
        raise WebhookError(500, "Deploy command is invalid")
    script = Path(script_value)
    if not script.is_absolute():
        raise WebhookError(500, "Deploy command is invalid")
    secure_regular_file(script, executable=True)

    try:
        with launch_log.open("ab", buffering=0) as output:
            process = subprocess.Popen(
                ["/usr/bin/sudo", "-n", "-u", user, "--", str(script)],
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                close_fds=True,
                start_new_session=True,
                env={"PATH": SAFE_PATH, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
            )
    except OSError as error:
        raise WebhookError(503, "Could not start deployment", str(error)) from error
    try:
        return_code = process.wait(timeout=0.25)
    except subprocess.TimeoutExpired:
        return process.pid
    if return_code != 0:
        raise WebhookError(
            503,
            "Deploy command was rejected",
            f"Deploy launcher exited immediately with {return_code}",
        )
    return process.pid


def main() -> tuple[int, str]:
    config = load_config()
    setup_logging(config)

    if os.environ.get("REQUEST_METHOD") != "POST":
        raise WebhookError(405, "Only POST is allowed")
    content_type = os.environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise WebhookError(400, "Content-Type must be application/json")

    maximum = config.get("max_payload_bytes", 1_048_576)
    if not isinstance(maximum, int) or not 1 <= maximum <= 4_194_304:
        raise WebhookError(500, "Webhook payload limit is invalid")
    payload_bytes = read_payload(maximum)
    try:
        payload = json.loads(payload_bytes)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise WebhookError(400, "Webhook payload is not valid JSON") from error
    if not isinstance(payload, dict):
        raise WebhookError(400, "Webhook payload is invalid")

    repository_value = payload.get("repository")
    repository = (
        repository_value.get("full_name") if isinstance(repository_value, dict) else None
    )
    if not isinstance(repository, str):
        raise WebhookError(400, "Webhook repository is missing")
    project, refs = configured_project(config, repository)

    secret_value = project.get("secret_file")
    if not isinstance(secret_value, str) or not Path(secret_value).is_absolute():
        raise WebhookError(500, "Webhook secret path is invalid")
    verify_signature(Path(secret_value), payload_bytes)

    event = os.environ.get("HTTP_X_GITHUB_EVENT", "")
    delivery = os.environ.get("HTTP_X_GITHUB_DELIVERY", "")
    if DELIVERY_RE.fullmatch(delivery) is None:
        raise WebhookError(400, "Webhook delivery id is invalid")
    if event == "ping":
        logging.info("Accepted signed ping delivery=%s repository=%s", delivery, repository)
        return 200, "Signed GitHub ping accepted"
    if event != "push":
        logging.info("Ignored signed event=%s delivery=%s", event, delivery)
        return 202, "Signed event ignored"

    ref = payload.get("ref")
    target = refs.get(ref) if isinstance(ref, str) else None
    if not isinstance(target, dict):
        logging.info("Ignored ref=%r repository=%s delivery=%s", ref, repository, delivery)
        return 202, "Push ref is not configured"
    if payload.get("deleted") is True:
        return 202, "Deleted ref ignored"

    launch_log_value = config.get("launch_log")
    if not isinstance(launch_log_value, str) or not Path(launch_log_value).is_absolute():
        raise WebhookError(500, "Webhook launch log is invalid")
    pid = launch_deploy(target, Path(launch_log_value))
    logging.info(
        "Deployment queued repository=%s ref=%s delivery=%s pid=%s",
        repository,
        ref,
        delivery,
        pid,
    )
    return 202, "Deployment queued"


if __name__ == "__main__":
    try:
        status_code, response_message = main()
    except WebhookError as error:
        logging.error("Webhook rejected: %s", error)
        status_code, response_message = error.status, error.public_message
    except Exception:
        logging.exception("Unhandled webhook failure")
        status_code, response_message = 500, "Webhook failed"
    respond(status_code, response_message)
