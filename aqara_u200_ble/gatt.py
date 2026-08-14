"""GATT client abstraction for transport-independent Aqara U200 protocol.

This module defines the typed interface that the session layer depends on,
allowing the library to work with any BLE transport (Bleak, Bumble, or a
custom implementation) without tight coupling to a specific implementation.

The interface is defined using `typing.Protocol` (structural typing) to enable:
- `BleakClient` to satisfy the interface without explicit subclassing
- `BumbleGattAdapter` to continue working unchanged
- Test mocks to work naturally without any boilerplate
- Home Assistant Bluetooth Manager integration in the future
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    pass


class GattClient(Protocol):
    """Minimal typed interface for GATT operations required by the session layer.

    This protocol defines the structural interface that `run_authenticated_lock_operation`
    depends on. Any object implementing these methods can be used as a client,
    regardless of the underlying BLE transport (Bleak, Bumble, native OS, etc.).

    The interface is intentionally minimal: only the methods actually used by the
    session are included. Optional low-level capabilities (MTU negotiation,
    connection parameter updates, etc.) are discovered dynamically via `getattr()`,
    not enforced by this protocol.

    Implementations:
    - `BleakClient` (from the bleak library) satisfies this protocol structurally
    - `BumbleGattAdapter` (aqara_u200_ble.bumble_transport) wraps Bumble's Peer
    - Test mocks can implement this interface without external dependencies
    """

    async def write_gatt_char(
        self,
        char_specifier: str,
        data: bytes,
        response: bool = False,
    ) -> None:
        """Write data to a GATT characteristic.

        Args:
            char_specifier: UUID string (128-bit or 16-bit short form) identifying
                the characteristic to write to. Both "0000ff07-0000-1000-8000-00805f9b34fb"
                and "ff07" formats are supported by implementations.
            data: Bytes to write. The size must fit within the connection's MTU.
            response: If True, wait for a GATT Write Response. If False, send a
                Write Command without waiting (faster, but no confirmation of
                success from the device).

        Raises:
            Implementations may raise exceptions on I/O errors, disconnection,
            or invalid characteristic UUID.
        """
        ...

    async def start_notify(
        self,
        char_specifier: str,
        callback: Callable[[Any, bytearray], None],
    ) -> None:
        """Enable notifications on a GATT characteristic.

        When the characteristic's value changes on the server, the callback will
        be invoked with the updated value.

        Args:
            char_specifier: UUID string identifying the characteristic.
            callback: A callable that receives (sender_object, data: bytearray)
                when a notification arrives. The sender_object is implementation-
                specific and is typically ignored by session code.

        Raises:
            Implementations may raise exceptions if the characteristic does not
            support notifications, or on I/O errors.
        """
        ...

    async def stop_notify(
        self,
        char_specifier: str,
    ) -> None:
        """Disable notifications on a GATT characteristic.

        Args:
            char_specifier: UUID string identifying the characteristic.

        Raises:
            Implementations may raise exceptions on I/O errors. Best-effort
            implementations tolerate failures (e.g., if the characteristic was
            never subscribed to).
        """
        ...


class AdvancedGattClient(GattClient, Protocol):
    """Extended GATT interface for low-level BLE operations.

    This protocol extends `GattClient` with optional, best-effort capabilities
    that are used dynamically (via `getattr()` checks) by the session layer.
    Implementations do not need to support all methods — those missing are
    simply skipped during session initialization.

    These methods are discovered at runtime because:
    1. Not all BLE stacks expose them (e.g., bleak relies on the OS)
    2. The session layer tolerates their absence without functional impact
    3. Test mocks can selectively enable/disable them to verify best-effort behavior
    """

    async def get_remote_le_features(self) -> int:
        """Read the remote device's LE feature flags via HCI.

        Returns an integer encoding the LE features bitmap (Bluetooth Core Vol 6
        Part B 4.2.1). Used to verify the lock's capabilities before attempting
        advanced operations.

        This is a best-effort operation — absence does not prevent the session
        from proceeding.

        Raises:
            Implementations may raise exceptions if the remote device disconnects
            or the HCI command times out.
        """
        ...

    async def request_mtu(self, mtu: int) -> int:
        """Request a new ATT MTU (Maximum Transmission Unit) size.

        Sends an ATT Exchange MTU Request to negotiate a larger MTU, allowing
        larger GATT reads/writes in a single operation. Returns the negotiated
        MTU accepted by the remote device.

        This is a best-effort operation — absence does not prevent the session
        from proceeding (the OS may have already negotiated an MTU).

        Args:
            mtu: The desired MTU size to request.

        Returns:
            The MTU size accepted by the remote device (may be less than requested).

        Raises:
            Implementations may raise exceptions on negotiation failure or timeout.
        """
        ...

    async def read_by_type(self, uuid16: int) -> list[bytes]:
        """Read all values of characteristics matching a 16-bit UUID type.

        Sends an ATT Read by Type Request to find all characteristics with a
        given 16-bit UUID and return their values without requiring handles.
        This is part of the GATT Robust Caching preamble (Bluetooth Core Vol 3
        Part G 2.5.2) and is used to read standard attributes like Appearance
        (0x2A01) and Database Hash (0x2B2A) without hard-coding their handles.

        Only Bumble exposes this operation. BleakClient and native OS stacks
        handle GATT discovery differently. Absence does not prevent the session
        from proceeding.

        Args:
            uuid16: 16-bit UUID type code to search for.

        Returns:
            A list of byte strings, one per matching characteristic value.
            Returns an empty list if no matches are found.

        Raises:
            Implementations may raise exceptions on I/O errors.
        """
        ...

    async def write_by_type(self, uuid16: int, data: bytes, response: bool = True) -> None:
        """Write to a characteristic identified by its 16-bit UUID type.

        Sends an ATT Write Request to a characteristic with the given 16-bit UUID,
        without requiring its full handle. Used to write standard attributes like
        Client Supported Features (0x2B29) as part of the GATT Robust Caching
        preamble.

        Only Bumble exposes this operation. BleakClient and native OS stacks
        do not allow direct handle-free writes. Absence does not prevent the
        session from proceeding (the OS may handle this automatically, as macOS
        and Android do).

        Args:
            uuid16: 16-bit UUID type code to write to.
            data: Bytes to write.
            response: If True, wait for a Write Response. If False, send a
                Write Command.

        Raises:
            Implementations may raise exceptions on I/O errors.
        """
        ...

    async def set_data_length(self, *, tx_octets: int, tx_time: int) -> None:
        """Request LE Data Length Extension (larger packets).

        Sends an HCI LE Set Data Length command to negotiate larger link-layer
        packet sizes. This allows the connection to handle larger GATT PDUs with
        fewer fragments. Replicated from the observed Android handshake (Bluetooth
        Core Vol 6 Part B 4.5.10).

        Only Bumble exposes this operation. Native OS stacks handle packet sizing
        automatically. Absence does not prevent the session from proceeding — the
        controller may already have negotiated larger packets on its own.

        Args:
            tx_octets: Desired TX packet size in octets.
            tx_time: Desired TX packet time in microseconds.

        Raises:
            Implementations may raise exceptions on timeout or device disconnection.
        """
        ...

    async def update_connection_parameters(
        self, *, interval_ms: float, latency: int, supervision_timeout_ms: float
    ) -> None:
        """Request a LE Connection Parameter Update.

        Sends an HCI LE Connection Update command to negotiate new connection
        parameters (interval, latency, supervision timeout). Replicated from
        the observed Android handshake (Bluetooth Core Vol 6 Part B 4.5.1).

        Only Bumble exposes this operation. Native OS stacks handle connection
        parameters automatically. Absence does not prevent the session from
        proceeding — the device may have already applied suitable parameters.

        Args:
            interval_ms: Desired connection interval in milliseconds.
            latency: Desired slave latency in connection events.
            supervision_timeout_ms: Desired supervision timeout in milliseconds.

        Raises:
            Implementations may raise exceptions on timeout or device disconnection.
        """
        ...
