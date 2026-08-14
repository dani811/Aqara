"""Pure-logic unit tests for the BLE auth handshake (feature 004).

These pin the project's central breakthrough — the header field is the
CRC-16/ARC of the body, not a random token — plus framing, fragmentation, and
AES-CCM control crypto. No BLE, no network, and no captured session secret: the
handshake body below is an ephemeral EC *public* key (public by definition), and
the AES-CCM key/nonce are throwaway fixtures.
"""

from __future__ import annotations

import pytest

from aqara_u200_ble import (
    build_auth_message,
    crc16_aqara,
    decrypt_control_payload,
    encrypt_control_payload,
    parse_auth_message,
)
from aqara_u200_ble.session import assemble_auth_fragments, fragment_auth_message

# A captured 0610 frame: 18-byte header + 65-byte public-key body.
# Header[7:9] = ed15 = CRC-16/ARC of the body (little-endian) — the discovery.
CAPTURED_0610 = bytes.fromhex(
    "00061001004100ed1500000000000000000004693eca158eb80556241a09327e"
    "6b7ac17e570610139ced094e992db17e4da31001333ff326a6f55fde91184537"
    "57ea83742eac69c2097d641188f72d115f2337"
)
CAPTURED_BODY = CAPTURED_0610[18:]


def test_crc16_matches_captured_frame() -> None:
    # THE breakthrough: the mystery header field is CRC-16/ARC of the body.
    assert len(CAPTURED_BODY) == 65
    assert crc16_aqara(CAPTURED_BODY) == 0x15ED


def test_build_auth_message_layout_and_crc() -> None:
    frame = build_auth_message(0x06, body=CAPTURED_BODY)
    assert frame[0:2] == bytes.fromhex("0006")
    assert frame[2:5] == bytes.fromhex("100100")
    assert frame[5:7] == (65).to_bytes(2, "little")  # body length
    assert frame[7:9] == (0x15ED).to_bytes(2, "little")  # CRC-16/ARC, little-endian
    assert frame[18:] == CAPTURED_BODY


def test_app_token_argument_is_ignored() -> None:
    # Backward-compatible arg exists but the CRC governs the wire (FR-003).
    without = build_auth_message(0x06, body=CAPTURED_BODY)
    with_token = build_auth_message(0x06, body=CAPTURED_BODY, app_token=0xABCD)
    assert without == with_token
    assert with_token[7:9] == (0x15ED).to_bytes(2, "little")


def test_build_rejects_unsupported_frame_type() -> None:
    with pytest.raises(ValueError):
        build_auth_message(0x05, body=b"\x00")


def test_build_parse_roundtrip_preserves_fields() -> None:
    payload = bytes.fromhex("1569ea835832a87a")
    message = build_auth_message(0x07, body=payload, lock_token=0)
    parsed = parse_auth_message(message)
    assert parsed.frame_type == 0x07
    assert parsed.lock_token == 0
    assert parsed.body == payload
    # The header field parses back as the body's CRC (formerly "app_token").
    assert parsed.app_token == crc16_aqara(payload)


def test_fragmentation_roundtrip_is_identity() -> None:
    fragments = fragment_auth_message(CAPTURED_0610, direction=0x5A)
    inbound = [bytes((0xDA, frag[1])) + frag[2:] for frag in fragments]
    reassembled = assemble_auth_fragments(inbound, expected_direction=0xDA)
    assert reassembled == CAPTURED_0610


def test_assemble_rejects_unexpected_direction() -> None:
    fragments = fragment_auth_message(CAPTURED_0610, direction=0x5A)
    with pytest.raises(ValueError):
        assemble_auth_fragments(fragments, expected_direction=0xDA)


def test_control_payload_aes_ccm_roundtrip() -> None:
    # Throwaway fixtures — not a captured session key/nonce.
    session_key_hex = "000102030405060708090a0b0c0d0e0f"  # 16 bytes
    nonce_hex = "0102030405060708090a0b0c0d"  # 13 bytes
    plaintext = bytes.fromhex("2f012f")
    ciphertext = encrypt_control_payload(session_key_hex, nonce_hex, plaintext=plaintext)
    # AES-CCM with a 4-byte tag: ciphertext is plaintext length + 4.
    assert len(ciphertext) == len(plaintext) + 4
    recovered = decrypt_control_payload(session_key_hex, nonce_hex, ciphertext=ciphertext)
    assert recovered == plaintext
