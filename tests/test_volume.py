"""Pure-logic unit tests for voice-volume control (feature 003).

The volume requests are captured control frames; serialization reuses feature
002's ControlRequest. Dispatch runs through an in-memory fake transport.
"""

from __future__ import annotations

import pytest

from aqara_ble import (
    VoiceVolumePreset,
    build_voice_volume_write,
    normalize_voice_volume_preset,
    set_voice_volume,
)


class FakeControlTransport:
    """Captures raw control bytes written to the lock."""

    def __init__(self) -> None:
        self.written: list[bytes] = []

    def write(self, payload: bytes) -> None:
        self.written.append(payload)


def test_build_high_volume_serializes_to_captured_bytes() -> None:
    write = build_voice_volume_write("high")
    assert write.preset is VoiceVolumePreset.HIGH
    # kind|command|body|trailer for the captured HIGH request.
    assert write.bytes == bytes.fromhex("01d302d23e165faddd09")


def test_build_medium_volume_serializes_to_captured_bytes() -> None:
    write = build_voice_volume_write("medium")
    assert write.bytes == bytes.fromhex("01d302d13e15d5fddfe4")


@pytest.mark.parametrize("preset", ["high", "alto", "HIGH"])
def test_alias_and_case_insensitive(preset: str) -> None:
    assert normalize_voice_volume_preset(preset) is VoiceVolumePreset.HIGH


def test_unsupported_preset_raises() -> None:
    with pytest.raises(ValueError):
        normalize_voice_volume_preset("whisper")


def test_set_volume_dispatches_exact_bytes() -> None:
    transport = FakeControlTransport()
    write = set_voice_volume(transport, "high")
    assert transport.written == [bytes.fromhex("01d302d23e165faddd09")]
    assert write.preset is VoiceVolumePreset.HIGH
