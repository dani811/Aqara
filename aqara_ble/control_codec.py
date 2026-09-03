# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# This file is part of Aqara BLE, licensed under the GNU Affero General Public
# License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
# distributed or network-served derivative must stay licensed under the AGPL
# and keep this notice. See the LICENSE file for the full terms.

"""AES-CCM control-channel codec for the U200 — pure, no I/O (feature 028).

Extracted from ``session.py``: the encrypt/decrypt of the AES-CCM control payload
(``tag_length=4``, empty AAD), keyed by the cloud-derived session key and nonce.
``cryptography`` is imported lazily inside the functions (as before) so importing
this module never requires the optional dependency until a call is made.

Constitution Principle II — the cipher parameters (tag length, empty AAD) are
byte-exact to the real lock and MUST NOT change.
"""

from __future__ import annotations


def encrypt_control_payload(
    session_key_hex: str,
    nonce_hex: str,
    *,
    plaintext: bytes,
) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESCCM  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Falta la dependencia opcional 'cryptography' para cifrado AES-CCM."
        ) from exc
    aes = AESCCM(bytes.fromhex(session_key_hex), tag_length=4)
    return aes.encrypt(bytes.fromhex(nonce_hex), plaintext, b"")


def decrypt_control_payload(
    session_key_hex: str,
    nonce_hex: str,
    *,
    ciphertext: bytes,
) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESCCM  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Falta la dependencia opcional 'cryptography' para descifrado AES-CCM."
        ) from exc
    aes = AESCCM(bytes.fromhex(session_key_hex), tag_length=4)
    return aes.decrypt(bytes.fromhex(nonce_hex), ciphertext, b"")
