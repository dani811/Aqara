"""Model identification from the advertisement (feature 016, US1)."""

from __future__ import annotations

from aqara_ble import (
    MODEL_BY_PRODUCT_ID,
    decode_manufacturer_payload,
    identify_candidate,
)

# The real U200 manufacturer (0x0B27) payload captured 2026-08-17.
U200_PAYLOAD = bytes.fromhex("2808039c5115f2802a109d2280")


def test_decodes_u200_product_and_model() -> None:
    product_id, model = decode_manufacturer_payload(U200_PAYLOAD)
    assert product_id == 0x9C03 and model == "U200"
    assert MODEL_BY_PRODUCT_ID[0x9C03] == "U200"


def test_short_payload_is_undecodable() -> None:
    assert decode_manufacturer_payload(b"\x28\x08\x03") == (None, None)
    assert decode_manufacturer_payload(b"") == (None, None)
    assert decode_manufacturer_payload(None) == (None, None)


def test_unknown_product_has_no_model() -> None:
    product_id, model = decode_manufacturer_payload(bytes.fromhex("2808ff7f00"))
    assert product_id == 0x7FFF and model is None  # decoded, but never invented


def test_candidate_exposes_payload_product_and_model() -> None:
    c = identify_candidate(
        address="CA:FE:00:00:00:01",
        name="DoorLocker",
        rssi=-55,
        manufacturer_data={0x0B27: U200_PAYLOAD},
    )
    assert c is not None
    assert c.manufacturer_payload == U200_PAYLOAD
    assert c.product_id == 0x9C03 and c.model == "U200"
    # Identification info is additive: it must not change reasons/score.
    assert "manufacturer" in c.reasons


def test_candidate_without_manufacturer_has_no_model() -> None:
    c = identify_candidate(
        address="CA:FE:00:00:00:01", name="DoorLocker", rssi=-55, service_uuids=("fcb9",)
    )
    assert c is not None and c.product_id is None and c.model is None
    assert c.manufacturer_payload == b""
