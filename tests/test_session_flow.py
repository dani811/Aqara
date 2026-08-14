"""Choreography tests for the authenticated unlock flow (feature 007).

These drive `run_authenticated_lock_operation` end to end against a scripted
stand-in for the lock. No radio, no network, no hardware: the fake answers
through the very notify callbacks the session hands it, and the two cloud calls
are replaced by fixtures.

What this proves: the *order* of the exchange, the tolerance of the lock's empty
ACKs, the failure messages, the best-effort nature of the optional low-level
transport capabilities, and the subscription cleanup.

What it does NOT prove: that a real U200 accepts the sequence. The fake answers
what the captures say the lock answers; only the live tutorial run is evidence
about the radio, the timing, and the lock's firmware.

No real secret appears here (Principle I): the EC key is public material by
definition and the AES-CCM key/nonce are throwaway fixtures.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from aqara_u200_ble import decrypt_control_payload, encrypt_control_payload, session
from aqara_u200_ble.session import (
    AUTH_NOTIFY_UUID,
    AUTH_WRITE_UUID,
    CONTROL_WRITE_UUID,
    PRE_AUTH_NOTIFY_ORDER,
    build_auth_message,
    fragment_auth_message,
    parse_auth_message,
)

# ── Throwaway fixtures. None of these is real material. ──────────────────────

# An uncompressed EC public key (0x04 + X + Y), 65 bytes. Public by definition.
FAKE_LOCK_PUBLIC_KEY = bytes([0x04]) + bytes(range(1, 65))
FAKE_CLOUD_PUBLIC_KEY_HEX = (bytes([0x04]) + bytes(range(65, 129))).hex()
FAKE_SESSION_KEY_HEX = "000102030405060708090a0b0c0d0e0f"
FAKE_NONCE_HEX = "0102030405060708090a0b0c0d"
FAKE_VERIFY_DATA_HEX = "aabbccddeeff00112233445566778899"

LOCK_DIRECTION = 0xDA


def short(uuid: str) -> str:
    """`0000ff62-2333-…` -> `ff62`, the vendor short id used in the captures."""

    return uuid[4:8]


CONTROL_RESPONSE_PLAINTEXT = b"\x20\x03\x20\x00"


@dataclass
class LockScript:
    """How the stand-in lock answers (see data-model.md)."""

    empty_acks_before_key: int = 0
    send_public_key: bool = True
    verify_ack_frame_type: int = 0x07
    control_response: bytes | None = CONTROL_RESPONSE_PLAINTEXT
    truncate_control_response: bool = False
    optional_capabilities: str = "none"  # none | present | failing


class FakeLockClient:
    """A scripted stand-in for the lock, consumed exactly like a bleak client.

    Optional low-level members are attached dynamically in `__init__` so that
    "absent" is expressed the way a real plain client expresses it — by simply
    not having the attribute, which is what `getattr(client, name, None)` sees.
    """

    def __init__(self, script: LockScript | None = None) -> None:
        self.script = script or LockScript()
        self.notify_callbacks: dict[str, Callable[[object, bytearray], None]] = {}
        self.events: list[str] = []
        self.written_frames: list[bytes] = []
        self.control_writes: list[bytes] = []
        self._auth_fragments: list[bytes] = []
        if self.script.optional_capabilities != "none":
            self._attach_optional_capabilities()

    # ── the surface the session requires ────────────────────────────────────

    async def start_notify(self, uuid: str, callback: Callable[[object, bytearray], None]) -> None:
        self.notify_callbacks[uuid] = callback
        self.events.append(f"notify:{short(uuid)}")

    async def stop_notify(self, uuid: str) -> None:
        self.events.append(f"stop_notify:{short(uuid)}")

    async def write_gatt_char(self, uuid: str, data: bytes, response: bool = True) -> None:
        if uuid == AUTH_WRITE_UUID:
            await self._on_auth_fragment(bytes(data))
        elif uuid == CONTROL_WRITE_UUID:
            self.events.append("write:control")
            self.control_writes.append(bytes(data))
            await self._answer_control()
        else:  # pragma: no cover - a write to an unexpected characteristic
            raise AssertionError(f"unexpected write to {uuid}")

    # ── the lock's side of the conversation ─────────────────────────────────

    async def _on_auth_fragment(self, fragment: bytes) -> None:
        self._auth_fragments.append(fragment)
        if fragment[1] != 0xFF:  # not the terminator yet
            return
        frame = b"".join(f[2:] for f in self._auth_fragments)
        self._auth_fragments.clear()
        self.events.append("write:auth")
        self.written_frames.append(frame)
        message = parse_auth_message(frame)
        if message.frame_type == 0x06:
            await self._answer_public_key_exchange()
        elif message.frame_type == 0x07:
            await self._answer_verify()

    async def _answer_public_key_exchange(self) -> None:
        for _ in range(self.script.empty_acks_before_key):
            await self._push_auth(build_auth_message(0x06, body=b""))
        if self.script.send_public_key:
            await self._push_auth(build_auth_message(0x06, body=FAKE_LOCK_PUBLIC_KEY))
        elif self.script.empty_acks_before_key == 0:
            # Never silent: an unresponsive lock still ACKs, it just never sends
            # the key. Keep the session's read loop fed so it exhausts its
            # retries instead of timing out (a different failure).
            for _ in range(8):
                await self._push_auth(build_auth_message(0x06, body=b""))

    async def _answer_verify(self) -> None:
        await self._push_auth(build_auth_message(self.script.verify_ack_frame_type, body=b""))

    async def _push_auth(self, frame: bytes) -> None:
        callback = self.notify_callbacks[AUTH_NOTIFY_UUID]
        for fragment in fragment_auth_message(frame, direction=LOCK_DIRECTION):
            callback(None, bytearray(fragment))

    async def _answer_control(self) -> None:
        if self.script.control_response is None:
            return
        callback = self.notify_callbacks.get(session.CONTROL_NOTIFY_UUID)
        if callback is None:  # pragma: no cover - control notify always enabled
            return
        if self.script.truncate_control_response:
            callback(None, bytearray(b"\x00"))
            return
        ciphertext = encrypt_control_payload(
            FAKE_SESSION_KEY_HEX,
            FAKE_NONCE_HEX,
            plaintext=self.script.control_response,
        )
        callback(None, bytearray(b"\x20" + ciphertext))

    # ── optional low-level capabilities (best-effort in production) ─────────

    def _attach_optional_capabilities(self) -> None:
        failing = self.script.optional_capabilities == "failing"

        def record(name: str) -> Callable[..., Any]:
            async def capability(*args: Any, **kwargs: Any) -> Any:
                self.events.append(name)
                if failing:
                    raise RuntimeError(f"{name} unsupported by this controller")
                return 247 if name == "mtu" else [b"\x00"]

            return capability

        self.get_remote_le_features = record("le_features")
        self.request_mtu = record("mtu")
        self.read_by_type = record("read_by_type")
        self.write_by_type = record("write_by_type")
        self.update_connection_parameters = record("conn_update")


# ── shared driver ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_real_sleeping(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The production sleeps pace CoreBluetooth writes — a radio concern.

    Waiting them out would add seconds to the suite and prove nothing about the
    choreography, so they become no-ops here (FR-009).
    """

    async def instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", instant)
    yield


@pytest.fixture
def _fake_cloud(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the two cloud calls at their binding site in `session`.

    `session.py` does `from .kdf import …`, so patching `kdf` would not
    intercept them (see research.md §2).
    """

    calls: list[str] = []

    def fake_public_key(**kwargs: Any) -> str:
        calls.append("cloud_get_public_key")
        return FAKE_CLOUD_PUBLIC_KEY_HEX

    def fake_session_material(**kwargs: Any) -> dict[str, str]:
        calls.append("get_session_material")
        return {
            "sessionKey": FAKE_SESSION_KEY_HEX,
            "nonce": FAKE_NONCE_HEX,
            "verifyData": FAKE_VERIFY_DATA_HEX,
        }

    monkeypatch.setattr(session, "cloud_get_public_key", fake_public_key)
    monkeypatch.setattr(session, "get_session_material", fake_session_material)
    return calls


def run_unlock(
    client: FakeLockClient, operation: str = "unlock", notify_timeout: float = 0.5
) -> Any:
    return asyncio.run(
        session.run_authenticated_lock_operation(
            client=client,
            device_id="fake-device",
            auth_headers=None,
            region="EU",
            base_url=None,
            operation=operation,
            notify_timeout=notify_timeout,
            signer=None,
        )
    )


def auth_frame_types(client: FakeLockClient) -> list[int]:
    return [parse_auth_message(frame).frame_type for frame in client.written_frames]


# ── User Story 1 — the sequence is guarded ───────────────────────────────────


def test_full_unlock_returns_material_write_and_response(_fake_cloud: list[str]) -> None:
    client = FakeLockClient()
    material, write, response = run_unlock(client)

    assert material.lock_public_key_hex == FAKE_LOCK_PUBLIC_KEY.hex()
    assert material.session_key_hex == FAKE_SESSION_KEY_HEX
    assert write.operation.name == "UNLOCK"
    assert response == CONTROL_RESPONSE_PLAINTEXT.hex()
    assert _fake_cloud == ["cloud_get_public_key", "get_session_material"]


def test_notifications_enabled_in_captured_order_before_any_write(
    _fake_cloud: list[str],
) -> None:
    client = FakeLockClient()
    run_unlock(client)

    # The literal captured order, NOT `PRE_AUTH_NOTIFY_ORDER` — asserting
    # against the constant would compare the code to itself and pass happily
    # while the order regressed (verified by mutation, see quickstart §2).
    enabled = [event for event in client.events if event.startswith("notify:")]
    assert enabled == ["notify:ff62", "notify:ff64", "notify:ff92", "notify:ff08"]
    first_write = next(i for i, e in enumerate(client.events) if e.startswith("write:"))
    last_notify = max(i for i, e in enumerate(client.events) if e.startswith("notify:"))
    assert last_notify < first_write


def test_write_order_is_pubkey_then_verify_then_control(_fake_cloud: list[str]) -> None:
    client = FakeLockClient()
    run_unlock(client)

    assert auth_frame_types(client) == [0x06, 0x07]
    writes = [event for event in client.events if event.startswith("write:")]
    assert writes == ["write:auth", "write:auth", "write:control"]


def test_control_write_carries_the_operation_prefix_and_ciphertext(
    _fake_cloud: list[str],
) -> None:
    client = FakeLockClient()
    _, write, _ = run_unlock(client)

    (control,) = client.control_writes
    assert control[0] == write.write_prefix
    plaintext = decrypt_control_payload(
        FAKE_SESSION_KEY_HEX, FAKE_NONCE_HEX, ciphertext=control[1:]
    )
    assert plaintext == write.payload


def test_the_public_key_frame_carries_the_cloud_key(_fake_cloud: list[str]) -> None:
    client = FakeLockClient()
    run_unlock(client)

    first = parse_auth_message(client.written_frames[0])
    assert first.body.hex() == FAKE_CLOUD_PUBLIC_KEY_HEX
    verify = parse_auth_message(client.written_frames[1])
    assert verify.body.hex() == FAKE_VERIFY_DATA_HEX


# ── User Story 2 — the lock's stalling stays tolerated ───────────────────────


def test_empty_acks_before_public_key_are_tolerated(_fake_cloud: list[str]) -> None:
    client = FakeLockClient(LockScript(empty_acks_before_key=3))
    material, _, _ = run_unlock(client)

    assert material.lock_public_key_hex == FAKE_LOCK_PUBLIC_KEY.hex()


def test_only_empty_acks_fails_with_specific_message(_fake_cloud: list[str]) -> None:
    client = FakeLockClient(LockScript(send_public_key=False))

    with pytest.raises(RuntimeError) as excinfo:
        run_unlock(client)

    message = str(excinfo.value)
    assert "clave publica" in message
    assert "ACKs" in message


def test_wrong_verify_ack_frame_type_is_rejected(_fake_cloud: list[str]) -> None:
    client = FakeLockClient(LockScript(verify_ack_frame_type=0x06))

    with pytest.raises(RuntimeError) as excinfo:
        run_unlock(client)

    message = str(excinfo.value)
    assert "0x07" in message
    assert "0x6" in message or "0x06" in message


# ── User Story 3 — a plain transport still works ─────────────────────────────


def test_unlock_without_any_optional_capability(_fake_cloud: list[str]) -> None:
    client = FakeLockClient(LockScript(optional_capabilities="none"))
    assert not hasattr(client, "request_mtu")

    material, _, _ = run_unlock(client)
    assert material.session_key_hex == FAKE_SESSION_KEY_HEX


def test_unlock_when_optional_capabilities_raise(_fake_cloud: list[str]) -> None:
    client = FakeLockClient(LockScript(optional_capabilities="failing"))

    material, _, _ = run_unlock(client)

    assert material.session_key_hex == FAKE_SESSION_KEY_HEX
    assert "mtu" in client.events  # attempted, failed, absorbed


def test_optional_capabilities_are_exercised_when_present(_fake_cloud: list[str]) -> None:
    client = FakeLockClient(LockScript(optional_capabilities="present"))
    run_unlock(client)

    optional = [e for e in client.events if e in {"le_features", "mtu", "conn_update"}]
    assert optional == ["le_features", "mtu", "conn_update"]
    first_notify = next(i for i, e in enumerate(client.events) if e.startswith("notify:"))
    assert client.events.index("conn_update") < first_notify


# ── User Story 4 — subscriptions are always released ─────────────────────────


def test_notifications_released_after_success(_fake_cloud: list[str]) -> None:
    client = FakeLockClient()
    run_unlock(client)

    for uuid in PRE_AUTH_NOTIFY_ORDER:
        assert f"stop_notify:{short(uuid)}" in client.events


def test_notifications_released_after_failure(_fake_cloud: list[str]) -> None:
    client = FakeLockClient(LockScript(send_public_key=False))

    with pytest.raises(RuntimeError):
        run_unlock(client)

    for uuid in PRE_AUTH_NOTIFY_ORDER:
        assert f"stop_notify:{short(uuid)}" in client.events


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_missing_control_response_is_tolerated(_fake_cloud: list[str]) -> None:
    # The write itself moves the bolt; a silent lock is not a failed unlock.
    client = FakeLockClient(LockScript(control_response=None))

    # The only genuinely elapsed wait in the suite: the session waits out its
    # notify timeout before concluding the lock said nothing. Kept short.
    _, _, response = run_unlock(client, notify_timeout=0.05)

    assert response is None


def test_truncated_control_response_is_rejected(_fake_cloud: list[str]) -> None:
    client = FakeLockClient(LockScript(truncate_control_response=True))

    with pytest.raises(RuntimeError) as excinfo:
        run_unlock(client)

    assert "demasiado corta" in str(excinfo.value)
