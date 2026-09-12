"""JSON brokers used by the legacy bot and the PWA realtime adapter.

The filename keeps its historical typo because several legacy modules import it.
New PWA code must inject a broker into its aiohttp application instead of using
``vmsh_nats``: that global remains a compatibility boundary for the game bot.

Core NATS is deliberately treated as transient fan-out, never as a durable log.
See ``vmshpwa/docs/realtime-offline-and-notifications.md`` and the Phase-0
integration harness in ``pwa_tests/test_nats_broker.py``.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import math
import re
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol, TypeAlias

import nats
import nats.aio.client
import nats.aio.subscription
import nats.errors
import orjson

from helpers.config import config, logger

__all__ = [
    "BrokerDeliveryError",
    "BrokerStateError",
    "InProcessBroker",
    "JsonBroker",
    "JsonPayloadError",
    "NATS",
    "NatsBroker",
    "SubjectError",
    "decode_json_payload",
    "encode_json_payload",
    "vmsh_nats",
]

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonCallback: TypeAlias = Callable[[JsonValue], Awaitable[None]]

NATS_SERVER = config.nats_server
NATS_TOPIC_PREFIX = config.config_name
_SUBJECT_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class JsonPayloadError(ValueError):
    """Raised when a broker payload is not strict, finite JSON."""


class SubjectError(ValueError):
    """Raised when a namespace or topic could escape its NATS subject scope."""


class BrokerStateError(RuntimeError):
    """Raised when an operation is attempted outside the broker lifecycle."""


class BrokerDeliveryError(RuntimeError):
    """Raised after every in-process subscriber ran and at least one failed."""

    def __init__(self, errors: Sequence[BaseException]):
        super().__init__(f"{len(errors)} broker subscriber(s) failed")
        self.errors = tuple(errors)


class JsonBroker(Protocol):
    """Small injectable contract shared by Core NATS and hermetic tests."""

    topic_prefix: str

    @property
    def nats_is_working(self) -> bool: ...

    async def setup(self, server_url: str | None = None) -> None: ...

    async def subscribe(self, topic: str, callback: JsonCallback) -> None: ...

    async def publish(self, topic: str, payload: JsonValue) -> None: ...

    async def ready(self) -> None: ...

    async def disconnect(self) -> None: ...


def _validate_json_value(value: Any, *, path: str = "$", depth: int = 0) -> None:
    # A depth cap protects both implementations from hostile recursive payloads.
    # This is transport validation, not a substitute for event-schema validation.
    if depth > 64:
        raise JsonPayloadError(f"JSON payload is nested too deeply at {path}")
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        if value < -(2**63) or value > 2**63 - 1:
            raise JsonPayloadError(
                f"JSON integer is outside signed 64-bit range at {path}"
            )
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise JsonPayloadError(f"JSON number must be finite at {path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]", depth=depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise JsonPayloadError(f"JSON object key must be a string at {path}")
            _validate_json_value(item, path=f"{path}.{key}", depth=depth + 1)
        return
    raise JsonPayloadError(f"Unsupported JSON value {type(value).__name__} at {path}")


def encode_json_payload(payload: JsonValue) -> bytes:
    """Validate and encode exactly the JSON subset accepted by both brokers."""

    _validate_json_value(payload)
    try:
        return orjson.dumps(payload)
    except (TypeError, orjson.JSONEncodeError) as error:
        raise JsonPayloadError("Could not encode broker JSON payload") from error


def decode_json_payload(data: bytes) -> JsonValue:
    """Decode untrusted NATS bytes and re-validate their JSON value tree."""

    try:
        payload = orjson.loads(data)
    except orjson.JSONDecodeError as error:
        raise JsonPayloadError("Broker message is not valid JSON") from error
    _validate_json_value(payload)
    return payload


def _validated_subject_part(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SubjectError(f"{label} must be a non-empty string")
    tokens = value.split(".")
    if any(not _SUBJECT_TOKEN.fullmatch(token) for token in tokens):
        raise SubjectError(
            f"{label} must use dot-separated ASCII alphanumeric, '-' or '_' tokens"
        )
    return value


def _subject(topic_prefix: str, topic: str, *, separator: str = ".") -> str:
    prefix = _validated_subject_part(topic_prefix, label="topic prefix")
    name = _validated_subject_part(topic, label="topic")
    result = f"{prefix}{separator}{name}"
    if len(result.encode("ascii")) > 255:
        raise SubjectError("NATS subject must be at most 255 ASCII bytes")
    return result


def _validate_callback(callback: JsonCallback) -> None:
    is_async = inspect.iscoroutinefunction(callback) or inspect.iscoroutinefunction(
        getattr(callback, "__call__", None)
    )
    if not is_async:
        raise TypeError("Broker callback must be declared with async def")


class InProcessBroker:
    """Hermetic JSON broker with the same serialize/deserialize boundary as NATS."""

    def __init__(self, topic_prefix: str):
        self.topic_prefix = _validated_subject_part(topic_prefix, label="topic prefix")
        self._subscriptions: dict[str, list[JsonCallback]] = defaultdict(list)
        self._active = False

    @property
    def nats_is_working(self) -> bool:
        """The in-process adapter is active but is not inter-process NATS."""

        return False

    @property
    def active(self) -> bool:
        return self._active

    async def setup(self, _server_url: str | None = None) -> None:
        # Setup is intentionally idempotent for aiohttp cleanup after partial startup.
        self._active = True

    async def subscribe(self, topic: str, callback: JsonCallback) -> None:
        if not self._active:
            raise BrokerStateError("Broker must be set up before subscribing")
        _validate_callback(callback)
        self._subscriptions[_subject(self.topic_prefix, topic)].append(callback)

    async def publish(self, topic: str, payload: JsonValue) -> None:
        if not self._active:
            raise BrokerStateError("Broker must be set up before publishing")
        # Round-tripping prevents hermetic tests from accepting values that the real
        # byte transport would change or reject.
        encoded_payload = encode_json_payload(payload)
        callbacks = tuple(
            self._subscriptions.get(_subject(self.topic_prefix, topic), ())
        )

        async def deliver(callback: JsonCallback) -> None:
            # Each NATS subscription decodes its own message object. Give hermetic
            # subscribers the same isolation so one callback cannot mutate another.
            await callback(decode_json_payload(encoded_payload))

        results = await asyncio.gather(
            *(deliver(callback) for callback in callbacks),
            return_exceptions=True,
        )
        errors = [result for result in results if isinstance(result, BaseException)]
        if errors:
            raise BrokerDeliveryError(errors)

    async def ready(self) -> None:
        """The in-memory subscription table is immediately authoritative."""

        if not self._active:
            raise BrokerStateError("Broker must be set up before readiness check")

    async def disconnect(self) -> None:
        # Clear callbacks even if setup never finished; repeated cleanup is a no-op.
        self._subscriptions.clear()
        self._active = False


class NatsBroker:
    """One-owner Core NATS connection with a strict per-instance namespace."""

    def __init__(
        self,
        topic_prefix: str,
        *,
        connect: Callable[..., Awaitable[nats.aio.client.Client]] = nats.connect,
    ):
        self.topic_prefix = _validated_subject_part(topic_prefix, label="topic prefix")
        self._connect = connect
        self._client: nats.aio.client.Client | None = None
        self._subscriptions: list[nats.aio.subscription.Subscription] = []
        self._server_url: str | None = None
        self._lifecycle_lock = asyncio.Lock()

    @property
    def nats_is_working(self) -> bool:
        client = self._client
        return bool(
            client is not None
            and getattr(client, "is_connected", False)
            and not getattr(client, "is_draining", False)
            and not getattr(client, "is_closed", False)
        )

    @property
    def active(self) -> bool:
        return self.nats_is_working

    async def setup(self, server_url: str | None = None) -> None:
        if not server_url:
            raise BrokerStateError("Core NATS broker requires an explicit server URL")
        async with self._lifecycle_lock:
            if self._client is not None and getattr(self._client, "is_closed", False):
                self._client = None
                self._server_url = None
                self._subscriptions.clear()
            if self._client is not None:
                if server_url != self._server_url:
                    raise BrokerStateError(
                        "Broker is already connected to another server"
                    )
                if getattr(self._client, "is_draining", False):
                    raise BrokerStateError("Broker connection is already draining")
                return

            nats_logger = logging.getLogger("nats")
            nats_logger.setLevel(logging.CRITICAL)
            client = await self._connect(
                server_url,
                connect_timeout=0.5,
                reconnect_time_wait=0.5,
                max_reconnect_attempts=100,
                name=f"vmsh:{self.topic_prefix}",
                pedantic=True,
            )
            self._client = client
            self._server_url = server_url

    async def subscribe(self, topic: str, callback: JsonCallback) -> None:
        _validate_callback(callback)
        client = self._require_client()
        subject = _subject(self.topic_prefix, topic)

        async def wrapped_callback(message) -> None:
            try:
                payload = decode_json_payload(message.data)
            except JsonPayloadError:
                logger.warning(
                    "Ignoring invalid JSON on isolated NATS subject %s",
                    subject,
                    exc_info=True,
                )
                return
            await callback(payload)

        subscription = await client.subscribe(subject, cb=wrapped_callback)
        self._subscriptions.append(subscription)

    async def publish(self, topic: str, payload: JsonValue) -> None:
        client = self._require_client()
        await client.publish(
            _subject(self.topic_prefix, topic), encode_json_payload(payload)
        )

    async def flush(self, *, timeout: float = 1.0) -> None:
        """Wait for server acknowledgement; mainly useful in integration probes."""

        await self._require_client().flush(timeout=timeout)

    async def ready(self) -> None:
        """Confirm that the server has processed subscriptions made at startup."""

        await self.flush()

    async def disconnect(self) -> None:
        async with self._lifecycle_lock:
            client = self._client
            if client is None:
                self._subscriptions.clear()
                self._server_url = None
                return

            try:
                if getattr(client, "is_closed", False):
                    pass
                elif getattr(client, "is_draining", False) or not getattr(
                    client, "is_connected", False
                ):
                    # nats-py rejects drain while reconnecting. An immediate close
                    # is the only bounded way to stop reconnect attempts at shutdown.
                    await client.close()
                else:
                    await client.drain()
            except (
                nats.errors.ConnectionClosedError,
                nats.errors.ConnectionDrainingError,
                nats.errors.ConnectionReconnectingError,
            ):
                if not getattr(client, "is_closed", False):
                    await client.close()
            except BaseException as drain_error:
                try:
                    if not getattr(client, "is_closed", False):
                        await client.close()
                except BaseException as close_error:
                    # Keep ``self._client`` for a later retry when neither graceful
                    # drain nor forced close could prove resource release.
                    raise BaseExceptionGroup(
                        "NATS drain and forced close both failed",
                        [drain_error, close_error],
                    ) from None
                self._client = None
                self._server_url = None
                self._subscriptions.clear()
                raise

            self._client = None
            self._server_url = None
            self._subscriptions.clear()

    def _require_client(self) -> nats.aio.client.Client:
        if (
            self._client is None
            or getattr(self._client, "is_closed", False)
            or not getattr(self._client, "is_connected", False)
        ):
            raise BrokerStateError("Core NATS broker is not connected")
        if getattr(self._client, "is_draining", False):
            raise BrokerStateError("Core NATS broker is draining")
        return self._client


class NATS:
    """Compatibility broker for legacy game modules.

    It retains the old underscore subject spelling and local fallback. PWA code
    must use ``NatsBroker``/``InProcessBroker`` directly and own its lifecycle.
    """

    def __init__(self, topic_prefix: str = NATS_TOPIC_PREFIX):
        self.topic_prefix = _validated_subject_part(topic_prefix, label="topic prefix")
        self.subsciptions: dict[str, Any] = {}
        self.nc: nats.aio.client.Client | None = None

    @property
    def nats_is_working(self) -> bool:
        client = self.nc
        return bool(
            client is not None
            and getattr(client, "is_connected", False)
            and not getattr(client, "is_draining", False)
            and not getattr(client, "is_closed", False)
        )

    async def setup(self, nats_server_url: str | None = NATS_SERVER) -> None:
        if self.nc is not None:
            if getattr(self.nc, "is_closed", False):
                self.nc = None
                self.subsciptions = {}
            else:
                return
        if nats_server_url is None:
            logger.warning("Работаем без nats-server.")
            logger.warning(
                "В таком режиме работа с несколькими процессами может быть некорректной"
            )
            return
        self.nats_server_url = nats_server_url
        logging.getLogger("nats").setLevel(logging.CRITICAL)
        try:
            client = await nats.connect(
                self.nats_server_url,
                connect_timeout=0.5,
                reconnect_time_wait=0.5,
                max_reconnect_attempts=2,
            )
        except nats.errors.NoServersError:
            logger.warning(
                "Не удалось подключиться к nats-server по адресу %r.",
                self.nats_server_url,
            )
            logger.warning("Работаем без nats-server.")
            logger.warning(
                "В таком режиме работа с несколькими процессами может быть некорректной"
            )
            return
        client.connect_timeout = 0.5
        client.reconnect_time_wait = 0.5
        client.max_reconnect_attempts = 100
        self.nc = client

    async def subscribe(self, topic: str, callback: JsonCallback) -> None:
        _validate_callback(callback)
        namespaced_topic = _subject(self.topic_prefix, topic, separator="_")

        async def wrapped_callback(message) -> None:
            await callback(decode_json_payload(message.data))

        if self.nats_is_working:
            assert self.nc is not None
            self.subsciptions[namespaced_topic] = await self.nc.subscribe(
                namespaced_topic, cb=wrapped_callback
            )
        else:
            self.subsciptions[namespaced_topic] = callback

    async def publish(self, topic: str, payload: JsonValue) -> None:
        namespaced_topic = _subject(self.topic_prefix, topic, separator="_")
        cloned_payload = decode_json_payload(encode_json_payload(payload))
        if self.nats_is_working:
            assert self.nc is not None
            await self.nc.publish(namespaced_topic, encode_json_payload(cloned_payload))
        elif namespaced_topic in self.subsciptions:
            await self.subsciptions[namespaced_topic](cloned_payload)

    async def disconnect(self) -> None:
        client = self.nc
        if client is None:
            self.subsciptions = {}
            return
        try:
            if getattr(client, "is_closed", False):
                pass
            elif getattr(client, "is_draining", False) or not getattr(
                client, "is_connected", False
            ):
                # nats-py cannot drain while reconnecting. The legacy adapter must
                # force-close in that state and keep the reference on double failure
                # so cleanup remains retryable.
                await client.close()
            else:
                await client.drain()
        except (
            nats.errors.ConnectionClosedError,
            nats.errors.ConnectionDrainingError,
            nats.errors.ConnectionReconnectingError,
        ):
            if not getattr(client, "is_closed", False):
                await client.close()
        except BaseException as drain_error:
            try:
                if not getattr(client, "is_closed", False):
                    await client.close()
            except BaseException as close_error:
                raise BaseExceptionGroup(
                    "Legacy NATS drain and forced close both failed",
                    [drain_error, close_error],
                ) from None
            self.nc = None
            self.subsciptions = {}
            raise

        self.nc = None
        self.subsciptions = {}


vmsh_nats = NATS()
