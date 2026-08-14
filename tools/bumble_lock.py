#!/usr/bin/env python3
"""Bloquear/desbloquear la U200 de forma AUTONOMA via ESP32 (controlador BLE) +
Bumble. Bumble puede emparejar (bonding), a diferencia de macOS CoreBluetooth.

Flujo: auth cloud con firma local -> intercambio BLE de claves -> verify cloud ->
sesion AES-CCM -> comando cifrado (LOCK=1f031f / UNLOCK=200320).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bumble.device import ConnectionParametersPreferences, Device, Peer
from bumble.hci import Phy
from bumble.transport import open_transport

from aqara_u200_ble import make_local_signer
from aqara_u200_ble.bumble_transport import BumbleGattAdapter
from aqara_u200_ble.session import (
    run_authenticated_lock_operation,
)


def _env(name: str) -> str:
    """Read a required config value from the environment (see .env.example).

    Secrets and device identifiers never live in source — fill them into a
    local, git-ignored .env and export it before running.
    """
    value = os.environ.get(name)
    if not value:
        raise SystemExit(
            f"Missing {name}. Copy .env.example to .env, fill it in, and export it "
            f"(e.g. `set -a; . ./.env; set +a`) before running."
        )
    return value


PORT = os.environ.get("AQARA_ESP32_PORT", "serial:/dev/cu.usbmodem0000,115200")
LOCK_MAC = _env("AQARA_LOCK_MAC")
DEVICE_ID = _env("AQARA_DEVICE_ID")

SIGNER = make_local_signer(
    appid=_env("AQARA_APPID"),
    appkey=_env("AQARA_APPKEY"),
    # Short-lived JWT captured from a logged-in app session; it rotates on
    # re-login, so re-capture into .env when the cloud returns code 108.
    token=_env("AQARA_TOKEN"),
    user_id=_env("AQARA_USER_ID"),
    client_id=_env("AQARA_CLIENT_ID"),
    phone_id=_env("AQARA_PHONE_ID"),
)


async def _run(operation: str) -> int:
    print(f"[*] Controlador ESP32: {PORT}", flush=True)
    async with await open_transport(PORT) as (source, sink):
        device = Device.with_hci("mac-esp32", "F0:F1:F2:F3:F4:F5", source, sink)
        await device.power_on()
        print(f"[*] Conectando a la U200 {LOCK_MAC} ...", flush=True)
        # Parametros de conexion INICIALES (LE Create Connection), no los de
        # la actualizacion posterior (esa la inicia la propia cerradura, ver
        # docs/ble-control-handoff.md §11.1). Verificados HOY contra el HCI
        # real de un movil Android: interval=36 unidades=45ms,
        # supervision_timeout=500 unidades=5000ms, latency=0. Bumble por
        # defecto pide 15-30ms/720ms -- nunca antes igualado (ver §11.13).
        real_conn_prefs = ConnectionParametersPreferences(
            connection_interval_min=45.0,
            connection_interval_max=45.0,
            max_latency=0,
            supervision_timeout=5000,
        )
        connection = await asyncio.wait_for(
            device.connect(
                LOCK_MAC,
                connection_parameters_preferences={Phy.LE_1M: real_conn_prefs},
            ),
            timeout=15.0,
        )
        print("[+] Conectado.", flush=True)
        try:
            # La U200 NO soporta bonding: 0 paquetes SMP observados en btsnoop
            # de la app real (docs/ble-control-handoff.md §6), y ademas se
            # confirmo en vivo (2026-08-11) que la cerradura CORTA LA CONEXION
            # en cuanto se le manda una solicitud SMP (connection.pair()),
            # incluso si esperamos su respuesta con timeout. No intentar
            # pairing en absoluto: ir directo a discovery, igual que la app.
            peer = Peer(connection)
            # NOTA: se probo un peer.request_mtu(247) explicito aqui (orden
            # real capturado: MTU antes que nada) pero colgo el proceso tras
            # una desconexion temprana de la cerradura (el request queda
            # pendiente y bloquea el semaforo interno de Bumble para SIEMPRE,
            # incluso con asyncio.wait_for). Se retira; el ATT MTU exchange
            # ocurre solo si Bumble lo hace por su cuenta. Ver
            # docs/ble-control-handoff.md §6.6 para retomarlo con cuidado
            # (p.ej. con un timeout duro a nivel de conexion, no de la
            # corutina).
            print("[*] Descubriendo servicios...", flush=True)
            await asyncio.wait_for(peer.discover_services(), timeout=15.0)
            for svc in peer.services:
                await asyncio.wait_for(peer.discover_characteristics(service=svc), timeout=10.0)
            print(f"[+] Servicios descubiertos: {len(peer.services)}", flush=True)
            adapter = BumbleGattAdapter(peer)

            material, write, response_hex = await run_authenticated_lock_operation(
                client=adapter,
                device_id=DEVICE_ID,
                auth_headers=None,
                region="EU",
                base_url=None,
                operation=operation,
                signer=SIGNER,
            )
            print("=" * 60)
            print(f"[OK] operacion={write.operation.name} plaintext={write.payload.hex()}")
            print(f"     sessionKey={material.session_key_hex} nonce={material.nonce_hex}")
            print(f"     respuesta_lock={response_hex}")
            print("=" * 60)
        finally:
            # disconnect() puede colgarse igual si la conexion ya se cayo por
            # su cuenta (espera un evento que nunca llega); nunca dejar que
            # esto bloquee el proceso para siempre.
            try:
                await asyncio.wait_for(connection.disconnect(), timeout=5.0)
            except Exception as exc:
                print(f"[!] disconnect() fallo/timeout: {exc!r}", flush=True)
    return 0


async def main() -> int:
    operation = sys.argv[1] if len(sys.argv) > 1 else "lock"
    # Salvaguarda global: cualquier colgado interno de Bumble (visto en vivo
    # 2026-08-11 con request_mtu tras una desconexion temprana) termina el
    # proceso con un error claro en vez de bloquear el bash del caller para
    # siempre. Ver docs/ble-control-handoff.md §6.6.
    try:
        return await asyncio.wait_for(_run(operation), timeout=45.0)
    except TimeoutError:
        print(
            "[!] TIMEOUT GLOBAL (45s): algo se colgo dentro de Bumble/la conexion. "
            "Reintenta (probablemente el ESP32/gadget necesite un ciclo limpio).",
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
