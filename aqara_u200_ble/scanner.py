"""Passive BLE scanning for Aqara U200 discovery."""

from __future__ import annotations

import asyncio
from typing import Any

AQARA_COMPANY_ID = 0x0B27
EXPECTED_NAME = "DoorLocker"


async def scan(seconds: float) -> None:
    try:
        from bleak import BleakScanner  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise SystemExit(
            "Falta la dependencia opcional 'bleak'. Instálala para usar el escáner."
        ) from exc

    print(
        f"Escaneo pasivo durante {seconds:g} s. "
        "No se conectará ni escribirá en ningún dispositivo."
    )
    seen: set[str] = set()

    def detection(device: Any, advertisement: Any) -> None:
        manufacturer = advertisement.manufacturer_data
        matches = (
            advertisement.local_name == EXPECTED_NAME
            or AQARA_COMPANY_ID in manufacturer
        )
        if not matches or device.address in seen:
            return
        seen.add(device.address)
        aqara_data = manufacturer.get(AQARA_COMPANY_ID, b"")
        print(
            f"candidato: nombre={advertisement.local_name!r} "
            f"dirección={device.address} RSSI={advertisement.rssi} "
            f"fabricante_0x0b27={aqara_data.hex() or '-'}"
        )

    async with BleakScanner(detection_callback=detection):
        await asyncio.sleep(seconds)
    if not seen:
        print(
            "No apareció ningún candidato. En la U200 observada fue necesario "
            "activar físicamente el teclado para que anunciase."
        )
