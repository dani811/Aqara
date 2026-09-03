# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# This file is part of Aqara BLE, licensed under the GNU Affero General Public
# License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
# distributed or network-served derivative must stay licensed under the AGPL
# and keep this notice. See the LICENSE file for the full terms.

"""Tests for the proven language-OTA primitives (aqara_ble.ota_language).

The AES-CCM vectors are REAL captures from a live Frida hook on BouncyCastle
CCMBlockCipher during a voice-pack download (2026-09-02) — they pin the OTA
crypto to standard AES-CCM under the session key+nonce (no ``expandedIv``).
"""
from __future__ import annotations

import pytest

from aqara_ble.ota_language import (
    crc16_mijia,
    crc16_xmodem,
    frame_data_block,
    iter_data_frames,
    ota_decrypt,
    ota_encrypt,
)

# --- CRC catalogue check values (input b"123456789") ------------------------


def test_crc16_xmodem_check_value():
    # Canonical CRC-16/XMODEM check value.
    assert crc16_xmodem(b"123456789") == 0x31C3


def test_crc16_mijia_is_modbus_check_value():
    # getMijiaCrc16String == CRC-16/MODBUS; canonical check value.
    assert crc16_mijia(b"123456789") == 0x4B37


# --- block framing ----------------------------------------------------------


def test_frame_data_block_shape():
    block = bytes(range(64))
    framed = frame_data_block(1, block)
    assert framed[:3] == bytes([0x02, 0x01, 0xFE])          # marker, 0xff-seq
    assert framed[3:3 + len(block)] == block
    assert framed[-2:] == crc16_xmodem(block).to_bytes(2, "big")


def test_frame_data_block_seq_wraps_one_byte():
    framed = frame_data_block(256, b"\x00")
    assert framed[:3] == bytes([0x02, 0x00, 0xFF])          # seq 256 -> 0x00


def test_iter_data_frames_pads_last_block_to_full_with_0x1a():
    blob = bytes(range(256)) * 8 + b"\xaa\xbb\xcc"          # 2048 + 3 bytes
    frames = list(iter_data_frames(blob, block_size=1024))
    assert len(frames) == 3
    # every block is now a FULL 1024 bytes — the final partial block is padded up
    # with 0x1a so the on-wire image is a whole number of blocks (the lock validates
    # the whole image against the declared MD5/CRC; a short tail → xfer abort).
    for f in frames:
        assert len(f[3:-2]) == 1024
    rebuilt = b"".join(f[3:-2] for f in frames)
    assert rebuilt[: len(blob)] == blob                    # real bytes preserved
    assert rebuilt[len(blob):] == b"\x1a" * (3072 - len(blob))
    assert frames[-1][3:-2] == b"\xaa\xbb\xcc" + b"\x1a" * 1021


# --- AES-CCM: REAL captured vectors (session key+nonce, 2026-09-02) ----------

_KEY = "ffd5e302ca27faba3fe1d2007e706765"
_NONCE = "78503198e7bae54bd4cefbad8b"


@pytest.fixture(autouse=True)
def _require_crypto():
    pytest.importorskip("cryptography")


def test_ota_encrypt_keepalive_vector():
    # HEART_PCK plaintext 2f012f -> captured ciphertext.
    assert ota_encrypt(_KEY, _NONCE, bytes.fromhex("2f012f")).hex() == "7b1db83eb71599"


def test_ota_encrypt_json_command_vector():
    # {"ID":255} OTA start short-pack plaintext -> captured ciphertext.
    pt = bytes.fromhex("047b224944223a3235357d00")          # \x04{"ID":255}\x00
    assert ota_encrypt(_KEY, _NONCE, pt).hex() == "5067b566cfeeb8be3fe5495451a3eb35"


def test_ota_decrypt_lock_status_frame():
    # Lock's progress report (ff92) ciphertext decrypts to the success JSON.
    ct = bytes.fromhex(
        "4467b566cfeeb8bc26f24c3257e2b45e6ae137e0f6a947875604617784cddb2c"
        "3224a81bbc33853cf5fa950dd01ea7426fcb1e70"
    )
    pt = ota_decrypt(_KEY, _NONCE, ct)
    assert b'"xfer_statu":"success"' in pt
    assert b'"progress":100' in pt


def test_ota_roundtrip():
    pt = b'\x04{"ID":42}\x00'
    assert ota_decrypt(_KEY, _NONCE, ota_encrypt(_KEY, _NONCE, pt)) == pt


def test_build_ota_file_info_matches_captured_manifest():
    from aqara_ble.ota_language import build_ota_file_info
    # 8 bytes -> crc32 hex string; shape + hex formatting.
    info = build_ota_file_info("x.bin", b"12345678")
    import zlib
    assert info == {"name": "x.bin", "size": 8, "crc32": format(zlib.crc32(b"12345678"), "x")}
    # captured manifest crc32 is hex(zlib.crc32) with no 0x, lowercase.
    assert build_ota_file_info("f", bytes(4))["crc32"] == format(zlib.crc32(bytes(4)), "x")


def test_build_ota_control_frame_matches_captured_id_frame():
    from aqara_ble.ota_language import build_ota_control_frame
    # {"ID":255} start command -> 0x90 || captured ciphertext.
    frame = build_ota_control_frame(_KEY, _NONCE, 0x04, b'{"ID":255}')
    assert frame.hex() == "90" + "5067b566cfeeb8be3fe5495451a3eb35"


def test_build_ota_manifest_json_matches_captured_fr_manifest():
    from aqara_ble.ota_language import build_ota_manifest_json
    blob = open("captures/U200_FR_audio_burn.bin", "rb").read()
    js = build_ota_manifest_json("U200_FR_audio_burn.bin", blob)
    assert js == (
        b'{"MCU_role":"receiver","file_info":{"name":"U200_FR_audio_burn.bin",'
        b'"size":1664596,"crc32":"14711156"}}'
    )


def test_iter_ota_data_writes_prefix_and_reconstruct():
    from aqara_ble.ota_language import iter_ota_data_writes, iter_data_frames
    blob = bytes(range(256)) * 6  # 1536 bytes -> 2 blocks
    writes = list(iter_ota_data_writes(blob, "x.bin", mtu_payload=200))
    assert all(w[0] == 0x11 for w in writes)
    assert writes[0][:4] == bytes([0x11, 0x01, 0x00, 0xff])  # init frame
    stream = b"".join(w[1:] for w in writes[1:])
    # per-block chunking: concatenated payloads reconstruct the framed blocks
    assert stream == b"".join(iter_data_frames(blob))
