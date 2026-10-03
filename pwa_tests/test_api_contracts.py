import asyncio
import json
import runpy
from dataclasses import replace
from pathlib import Path

import pytest

from apps import pwa_app
from helpers.config import config
from helpers.nats_brocker import InProcessBroker
from helpers.pwa.api_contracts import (
    build_api_error_payload,
    build_realtime_error_payload,
    build_runtime_payload,
    validate_runtime_instance,
)
from main import create_app


FIXTURES = Path("vmshpwa/packages/contracts/fixtures")


class HermeticPwaAdapter:
    @staticmethod
    def configure(app):
        pwa_app.configure(app, broker=InProcessBroker("contract-test"))


def _fixture(relative_path: str) -> dict:
    return json.loads((FIXTURES / relative_path).read_text(encoding="utf-8"))


@pytest.mark.parametrize("audience", ["student", "family", "staff"])
def test_python_runtime_builder_matches_typescript_fixture(audience):
    fixture = _fixture(f"runtime/{audience}.v1.json")
    response = fixture["response"]

    assert (
        build_runtime_payload(
            audience=audience,
            instance=response["instance"],
            server_time=response["serverTime"],
            request_id=response["requestId"],
            **response["features"],
        )
        == response
    )


@pytest.mark.parametrize(
    "fixture_name",
    ["unauthenticated.v1.json", "forbidden.v1.json", "conflict.v1.json"],
)
def test_python_error_builder_matches_typescript_fixture(fixture_name):
    fixture = _fixture(f"errors/{fixture_name}")
    error = fixture["response"]["error"]

    assert (
        build_api_error_payload(
            code=error["code"],
            message=error["message"],
            request_id=error["requestId"],
            details=error.get("details"),
        )
        == fixture["response"]
    )


def test_python_realtime_error_builder_matches_typescript_fixture():
    fixture = _fixture("realtime/invalid-json.v1.json")["response"]

    assert (
        build_realtime_error_payload(
            cursor=fixture["cursor"],
            server_time=fixture["serverTime"],
            code=fixture["code"],
            message=fixture["message"],
            request_id=fixture["requestId"],
        )
        == fixture
    )


@pytest.mark.parametrize(
    "value",
    [" Agent", "agent ", "AGENT", "agent:other", "agent/other", ".agent"],
)
def test_python_runtime_instance_rejects_same_unsafe_values_as_zod(value):
    with pytest.raises(ValueError, match="canonical lowercase ASCII"):
        validate_runtime_instance(value)


def test_app_composition_rejects_unsafe_browser_namespace():
    invalid_config = replace(config, pwa_instance="../human")

    with pytest.raises(ValueError, match="canonical lowercase ASCII"):
        create_app(
            [HermeticPwaAdapter],
            runtime_config=invalid_config,
        )


def test_direct_script_and_imported_adapter_share_the_same_app_key(monkeypatch):
    """Guard the actual ``python main.py`` module-name boundary without binding."""

    def finish_without_starting_server(coroutine):
        coroutine.close()

    monkeypatch.setattr(asyncio, "run", finish_without_starting_server)
    script_globals = runpy.run_path("main.py", run_name="__main__")

    assert pwa_app._runtime_config(script_globals["app"]) is config
