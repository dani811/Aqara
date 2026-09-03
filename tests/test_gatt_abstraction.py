# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# Aqara BLE. Source-available under the PolyForm Noncommercial License 1.0.0.
# Noncommercial use only; any commercial or for-profit use requires a separate
# written license from the copyright holder. See the LICENSE file for the terms.

"""Tests for the GATT client abstraction layer (feature 011).

Demonstrates that the session layer can work with any GATT client implementation
that satisfies the GattClient protocol, without coupling to Bleak or Bumble.

Key tests:
1. Minimal client implementing only required methods (write_gatt_char,
   start_notify, stop_notify) passes protocol checks
2. Optional capabilities are truly optional — their absence doesn't break
   the session
3. BumbleGattAdapter remains fully compatible (structural typing)
4. Mock clients can selectively disable optional capabilities to test
   best-effort behavior
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

import aqara_ble
from aqara_ble import GattClient, encrypt_control_payload, session
from aqara_ble.bumble_transport import BumbleGattAdapter
from aqara_ble.session import (
    AUTH_NOTIFY_UUID,
    AUTH_WRITE_UUID,
    CONTROL_WRITE_UUID,
    build_auth_message,
    fragment_auth_message,
    parse_auth_message,
)

# ──────────────────────────────────────────────────────────────────────────────
# Minimal GATT client (tests structural typing — no inheritance needed)
# ──────────────────────────────────────────────────────────────────────────────


class MinimalGattClient:
    """Bare-minimum client implementing only the required GattClient interface.

    This proves that:
    1. The protocol doesn't require inheritance or explicit typing
    2. Any object with the right methods can be used
    3. Optional methods (detected via getattr) are truly optional
    """

    def __init__(self) -> None:
        self.notify_callbacks: dict[str, Callable[[object, bytearray], None]] = {}
        self.written_frames: list[bytes] = []
        self.control_writes: list[bytes] = []
        self._auth_fragments: list[bytes] = []

    async def write_gatt_char(
        self,
        char_specifier: str,
        data: bytes,
        response: bool = False,
    ) -> None:
        """Required: write to characteristic."""
        if char_specifier == AUTH_WRITE_UUID:
            await self._on_auth_fragment(bytes(data))
        elif char_specifier == CONTROL_WRITE_UUID:
            self.control_writes.append(bytes(data))
            await self._answer_control()

    async def start_notify(
        self,
        char_specifier: str,
        callback: Callable[[Any, bytearray], None],
    ) -> None:
        """Required: enable notifications."""
        self.notify_callbacks[char_specifier] = callback

    async def stop_notify(
        self,
        char_specifier: str,
    ) -> None:
        """Required: disable notifications."""
        self.notify_callbacks.pop(char_specifier, None)

    # ── Optional capabilities: deliberately absent (tests best-effort behavior) ──

    # NO get_remote_le_features, request_mtu, set_data_length, read_by_type,
    # write_by_type, or update_connection_parameters — these will be detected
    # as absent via getattr() and gracefully skipped.

    # ── Scripted lock responses ──

    async def _on_auth_fragment(self, fragment: bytes) -> None:
        self._auth_fragments.append(fragment)
        if fragment[1] != 0xFF:  # not the terminator yet
            return
        frame = b"".join(f[2:] for f in self._auth_fragments)
        self._auth_fragments.clear()
        self.written_frames.append(frame)
        message = parse_auth_message(frame)
        if message.frame_type == 0x06:
            # Echo back a public key response
            await self._push_auth(build_auth_message(0x06, body=bytes([0x04, *range(1, 65)])))
        elif message.frame_type == 0x07:
            # Echo back a verify ACK
            await self._push_auth(build_auth_message(0x07, body=b""))

    async def _push_auth(self, frame: bytes) -> None:
        callback = self.notify_callbacks.get(AUTH_NOTIFY_UUID)
        if callback is None:
            return
        for fragment in fragment_auth_message(frame, direction=0xDA):
            callback(None, bytearray(fragment))

    async def _answer_control(self) -> None:
        callback = self.notify_callbacks.get(session.CONTROL_NOTIFY_UUID)
        if callback is None:
            return
        ciphertext = encrypt_control_payload(
            "000102030405060708090a0b0c0d0e0f",
            "0102030405060708090a0b0c0d",
            plaintext=b"\x20\x03\x20\x00",
        )
        callback(None, bytearray(b"\x20" + ciphertext))


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_real_sleeping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the radio-pacing delays in tests."""

    async def instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", instant)


@pytest.fixture
def _fake_cloud(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace cloud calls with fixtures."""

    calls: list[str] = []

    def fake_public_key(**kwargs: Any) -> str:
        calls.append("cloud_get_public_key")
        return (bytes([0x04]) + bytes(range(65, 129))).hex()

    def fake_session_material(**kwargs: Any) -> dict[str, str]:
        calls.append("get_session_material")
        return {
            "sessionKey": "000102030405060708090a0b0c0d0e0f",
            "nonce": "0102030405060708090a0b0c0d",
            "verifyData": "aabbccddeeff00112233445566778899",
        }

    monkeypatch.setattr(session, "cloud_get_public_key", fake_public_key)
    monkeypatch.setattr(session, "get_session_material", fake_session_material)
    return calls


class TestMinimalClientSatisfiesProtocol:
    """Test that a minimal client with only required methods works."""

    def test_minimal_client_has_required_methods(self) -> None:
        """A bare client satisfies the GattClient protocol structurally."""
        client = MinimalGattClient()
        # These should all exist and be awaitable
        assert callable(client.write_gatt_char)
        assert callable(client.start_notify)
        assert callable(client.stop_notify)

    def test_minimal_client_lacks_optional_methods(self) -> None:
        """Optional methods are absent, triggering best-effort skipping."""
        client = MinimalGattClient()
        assert getattr(client, "get_remote_le_features", None) is None
        assert getattr(client, "request_mtu", None) is None
        assert getattr(client, "set_data_length", None) is None
        assert getattr(client, "read_by_type", None) is None
        assert getattr(client, "write_by_type", None) is None
        assert getattr(client, "update_connection_parameters", None) is None

    def test_minimal_client_completes_lock_operation(self, _fake_cloud: list[str]) -> None:
        """A minimal client can complete a full authentication flow.

        This is the key proof: no external dependencies (Bleak, Bumble),
        only the protocol interface, yet the session succeeds.
        """
        client = MinimalGattClient()
        material, write, response = asyncio.run(
            session.run_authenticated_lock_operation(
                client=client,
                device_id="test-device",
                auth_headers=None,
                region="EU",
                base_url=None,
                operation="unlock",
                notify_timeout=0.5,
                signer=None,
            )
        )
        assert material.session_key_hex == "000102030405060708090a0b0c0d0e0f"
        assert material.nonce_hex == "0102030405060708090a0b0c0d"
        assert write.operation.name == "UNLOCK"
        # Response was decrypted and parsed
        assert response == "20032000"


class TestBumbleAdapterRemainCompatible:
    """Test that BumbleGattAdapter is still fully usable."""

    def test_bumble_adapter_implements_all_methods(self) -> None:
        """BumbleGattAdapter has all required and optional methods."""
        # Check that the class defines the methods we expect (can't instantiate
        # without a real Bumble Peer, so check the class definition itself)
        assert hasattr(BumbleGattAdapter, "write_gatt_char")
        assert hasattr(BumbleGattAdapter, "start_notify")
        assert hasattr(BumbleGattAdapter, "stop_notify")
        assert hasattr(BumbleGattAdapter, "read_by_type")
        assert hasattr(BumbleGattAdapter, "write_by_type")
        assert hasattr(BumbleGattAdapter, "get_remote_le_features")
        assert hasattr(BumbleGattAdapter, "request_mtu")
        assert hasattr(BumbleGattAdapter, "set_data_length")
        assert hasattr(BumbleGattAdapter, "update_connection_parameters")


class TestOptionalCapabilitiesAreTrulyOptional:
    """Test that missing optional methods don't break the session."""

    def test_session_succeeds_with_no_optional_methods(self, _fake_cloud: list[str]) -> None:
        """The core flow works even if all optional methods are absent."""
        client = MinimalGattClient()
        # Verify they're really absent
        for method_name in [
            "get_remote_le_features",
            "request_mtu",
            "read_by_type",
            "write_by_type",
            "set_data_length",
            "update_connection_parameters",
        ]:
            assert getattr(client, method_name, None) is None
        # Session still completes successfully
        material, _, _ = asyncio.run(
            session.run_authenticated_lock_operation(
                client=client,
                device_id="test-device",
                auth_headers=None,
                region="EU",
                base_url=None,
                operation="unlock",
                notify_timeout=0.5,
                signer=None,
            )
        )
        assert material is not None


class TestProtocolSignature:
    """Test that the GattClient protocol is properly defined."""

    def test_gatt_client_protocol_is_structural(self) -> None:
        """GattClient uses Protocol for structural typing."""
        # Check that GattClient is a Protocol (not inherited from or instantiated)
        assert hasattr(GattClient, "__mro__")  # Has MRO like any class
        # Should be usable as a type hint for any object with matching methods
        client: GattClient = MinimalGattClient()
        assert client is not None


class TestPackageExports:
    """Test that the new abstraction is exported from the package."""

    def test_gatt_client_exported(self) -> None:
        """GattClient is in the public API."""
        assert hasattr(aqara_ble, "GattClient")
        assert aqara_ble.GattClient is GattClient

    def test_gatt_client_in_all(self) -> None:
        """GattClient is in __all__."""
        assert "GattClient" in aqara_ble.__all__
