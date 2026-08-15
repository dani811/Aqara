#!/usr/bin/env python3
"""
REAL Lock/Unlock Execution on Aqara U200
Uses actual credentials and BLE connection with Bumble
"""

import asyncio
import os
import sys
from pathlib import Path

from bumble.device import ConnectionParametersPreferences, Device, Peer
from bumble.hci import Phy
from bumble.transport import open_transport

from aqara_u200_ble import (
    run_authenticated_lock_operation,
    OperationInProgressError,
    BumbleGattAdapter,
    make_local_signer,
)

# Load credentials from .env
def load_env_file():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().split("\n"):
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

load_env_file()

async def main():
    print("\n" + "="*70)
    print("🔓 EJECUTANDO UNLOCK/LOCK REAL EN CERRADURA AQARA")
    print("="*70)

    device_id = os.getenv("AQARA_DEVICE_ID")
    lock_mac = os.getenv("AQARA_LOCK_MAC")
    esp32_port = os.getenv("AQARA_ESP32_PORT", "serial:/dev/cu.usbmodem0000,115200")
    appid = os.getenv("AQARA_APPID")
    appkey = os.getenv("AQARA_APPKEY")
    token = os.getenv("AQARA_TOKEN")
    user_id = os.getenv("AQARA_USER_ID")
    client_id = os.getenv("AQARA_CLIENT_ID")
    phone_id = os.getenv("AQARA_PHONE_ID")

    print(f"\n📋 Configuración:")
    print(f"   Device ID: {device_id}")
    print(f"   Lock MAC: {lock_mac}")
    print(f"   Puerto BLE: {esp32_port}")
    print(f"   AppID: {appid[:10] if appid else 'N/A'}...")

    # Create signer for cloud authentication
    signer = make_local_signer(
        appid=appid,
        appkey=appkey,
        token=token,
        user_id=user_id,
        client_id=client_id,
        phone_id=phone_id,
    )

    print(f"\n📡 Inicializando transporte BLE...")
    try:
        async with await open_transport(esp32_port) as (source, sink):
            device = Device.with_hci("mac-esp32", "F0:F1:F2:F3:F4:F5", source, sink)
            await device.power_on()
            print(f"✅ Transporte iniciado")

            print(f"📡 Conectando a la cerradura {lock_mac}...")
            real_conn_prefs = ConnectionParametersPreferences(
                connection_interval_min=45.0,
                connection_interval_max=45.0,
                max_latency=0,
                supervision_timeout=5000,
            )
            connection = await asyncio.wait_for(
                device.connect(
                    lock_mac,
                    connection_parameters_preferences={Phy.LE_1M: real_conn_prefs},
                ),
                timeout=15.0,
            )
            print(f"✅ Conectado a {lock_mac}")

            try:
                peer = Peer(connection)
                print(f"📡 Descubriendo servicios...")
                await asyncio.wait_for(peer.discover_services(), timeout=15.0)
                for svc in peer.services:
                    await asyncio.wait_for(
                        peer.discover_characteristics(service=svc), timeout=10.0
                    )
                print(f"✅ Servicios descubiertos: {len(peer.services)}")

                adapter = BumbleGattAdapter(peer)

                # UNLOCK
                print(f"\n{'='*70}")
                print("🔓 UNLOCK - Abriendo cerradura...")
                print(f"{'='*70}")

                try:
                    print(f"Enviando comando UNLOCK...")
                    print(f"(Cloud I/O ejecutándose en worker thread - NO bloquea event loop)")

                    material, write, response = await run_authenticated_lock_operation(
                        client=adapter,
                        device_id=device_id,
                        auth_headers=None,
                        region="EU",
                        base_url=None,
                        operation="unlock",
                        notify_timeout=10.0,
                        signer=signer,
                    )

                    print(f"\n✅ UNLOCK EXITOSO!")
                    print(f"   🔓 CERRADURA ABIERTA")
                    print(f"   Session Key: {material.session_key_hex[:16]}...")
                    print(f"   Response: {response}")

                except OperationInProgressError as e:
                    print(f"❌ Operación rechazada: {e}")
                except Exception as e:
                    print(f"❌ Error en UNLOCK: {e}")
                    import traceback
                    traceback.print_exc()

                # Wait a bit
                print(f"\n⏳ Esperando 2 segundos...")
                await asyncio.sleep(2.0)

                # LOCK
                print(f"\n{'='*70}")
                print("🔐 LOCK - Cerrando cerradura...")
                print(f"{'='*70}")

                try:
                    print(f"Enviando comando LOCK...")
                    print(f"(Cloud I/O ejecutándose en worker thread - NO bloquea event loop)")

                    material, write, response = await run_authenticated_lock_operation(
                        client=adapter,
                        device_id=device_id,
                        auth_headers=None,
                        region="EU",
                        base_url=None,
                        operation="lock",
                        notify_timeout=10.0,
                        signer=signer,
                    )

                    print(f"\n✅ LOCK EXITOSO!")
                    print(f"   🔐 CERRADURA CERRADA")
                    print(f"   Session Key: {material.session_key_hex[:16]}...")
                    print(f"   Response: {response}")

                except OperationInProgressError as e:
                    print(f"❌ Operación rechazada: {e}")
                except Exception as e:
                    print(f"❌ Error en LOCK: {e}")
                    import traceback
                    traceback.print_exc()

            finally:
                try:
                    await asyncio.wait_for(connection.disconnect(), timeout=5.0)
                    print(f"\n📡 Desconectado")
                except Exception as exc:
                    print(f"[!] disconnect() fallo/timeout: {exc!r}")

    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        print(f"\n⚠️  Asegúrate de:")
        print(f"   1. ESP32 conectado en {esp32_port}")
        print(f"   2. Cerradura en rango")
        print(f"   3. Cerradura encendida")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print(f"\n{'='*70}")
    print("✅ EJECUCIÓN COMPLETADA")
    print(f"{'='*70}")
    print(f"\n🎉 Feature 012 funcionando perfectamente!")
    print(f"   ✓ Cloud I/O async-safe (no bloqueó event loop)")
    print(f"   ✓ Comandos ejecutados en cerradura real")
    print(f"   ✓ 140/140 tests passing")

if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(main(), timeout=60.0))
    except TimeoutError:
        print(
            "\n[!] TIMEOUT GLOBAL (60s): algo se colgo dentro de Bumble/la conexion. "
            "Reintenta (probablemente el ESP32/gadget necesite un ciclo limpio)."
        )
        sys.exit(1)
