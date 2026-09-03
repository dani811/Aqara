# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# Aqara BLE. Source-available under the PolyForm Noncommercial License 1.0.0.
# Noncommercial use only; any commercial or for-profit use requires a separate
# written license from the copyright holder. See the LICENSE file for the terms.

"""Pure-logic unit tests for the control-channel framing (feature 002).

These pin the observable framing behaviour against short, sanitized fragments of
real captures (Constitution Principles II & IV). No network, no BLE, no secrets.
"""

from __future__ import annotations

import binascii

import pytest

from aqara_ble import (
    ControlRequest,
    control_command_name,
    parse_control_request,
    valid_crc,
)

# Captured control frames (framing only — no account/session material).
VOICE_VOLUME_FRAME = bytes.fromhex("01d302d13e15d5fddfe4")
KEEPALIVE_FRAME = bytes.fromhex("01fe01fc158b3609")


def test_parses_voice_volume_request() -> None:
    request = parse_control_request(VOICE_VOLUME_FRAME)
    assert request.kind == 0x01
    assert request.command == 0xD3
    assert request.body == bytes.fromhex("02d13e15")
    assert request.trailer == bytes.fromhex("d5fddfe4")


def test_parses_keepalive_request() -> None:
    request = parse_control_request(KEEPALIVE_FRAME)
    assert request.command == 0xFE
    assert request.body == bytes.fromhex("01fc")
    assert request.trailer == bytes.fromhex("158b3609")


def test_rejects_too_short_control_request() -> None:
    with pytest.raises(ValueError):
        parse_control_request(bytes.fromhex("01d302d13e"))


def test_rejects_unrecognized_prefix() -> None:
    # Valid length but a prefix that is not a control request (0x01/0x03).
    with pytest.raises(ValueError):
        parse_control_request(bytes.fromhex("02d302d13e15d5fddfe4"))


@pytest.mark.parametrize("frame", [VOICE_VOLUME_FRAME, KEEPALIVE_FRAME])
def test_control_request_roundtrip_is_identity(frame: bytes) -> None:
    assert parse_control_request(frame).as_bytes() == frame


def test_control_request_as_bytes_from_parts() -> None:
    request = ControlRequest(
        kind=0x01, command=0xD3, body=bytes.fromhex("02d13e15"), trailer=bytes.fromhex("d5fddfe4")
    )
    assert request.as_bytes() == VOICE_VOLUME_FRAME


def test_command_name_known_and_fallback() -> None:
    assert control_command_name(0xD3) == "voice-volume-alert"
    assert control_command_name(0xFE) == "session-keepalive"
    # Unknown command -> stable, non-crashing label.
    assert control_command_name(0x7A) == "command-0x7a"


def test_valid_crc_accepts_captured_block() -> None:
    payload = bytes.fromhex("4c0000004a000000010000012e000000")
    crc = binascii.crc_hqx(payload, 0).to_bytes(2, "big")
    assert valid_crc(payload + crc) is True


def test_valid_crc_rejects_mutation() -> None:
    payload = b"bloque de prueba"
    crc = binascii.crc_hqx(payload, 0).to_bytes(2, "big")
    corrupt = bytes((payload[0] ^ 1,)) + payload[1:] + crc
    assert valid_crc(corrupt) is False


def test_valid_crc_rejects_too_short_input() -> None:
    assert valid_crc(b"") is False
    assert valid_crc(b"\x00") is False
