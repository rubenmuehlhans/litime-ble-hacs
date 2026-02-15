"""DataUpdateCoordinator for LiTime BMS BLE."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import struct
from typing import Any

from bleak import BleakClient, BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    BATTERY_STATE_CHARGE_DISABLED,
    BATTERY_STATE_CHARGING,
    BATTERY_STATE_DISCHARGING,
    CMD_CHARGE_OFF,
    CMD_CHARGE_ON,
    CMD_DISCHARGE_OFF,
    CMD_DISCHARGE_ON,
    CMD_QUERY_STATUS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_CELLS,
    MAX_MISSED_UPDATES,
    MIN_RESPONSE_LENGTH,
    NOTIFY_CHAR_UUID,
    PROTECTION_FLAGS,
    SERVICE_UUID,
    WRITE_CHAR_UUID,
)

_LOGGER = logging.getLogger(__name__)

# Response marker: byte[2] == 0x65 indicates a valid status response
RESPONSE_MARKER_OFFSET = 2
RESPONSE_MARKER_VALUE = 0x65


def _build_command(cmd: int) -> bytes:
    """Build an 8-byte command frame.

    Format: {0x00, 0x00, 0x04, 0x01, CMD, 0x55, 0xAA, CHECKSUM}
    Checksum = 0x04 + 0x01 + CMD = 0x05 + CMD
    """
    checksum = 0x04 + 0x01 + cmd
    return bytes([0x00, 0x00, 0x04, 0x01, cmd, 0x55, 0xAA, checksum & 0xFF])


def _decode_protection_flags(flags: int) -> str:
    """Decode protection flags to human-readable string."""
    if flags == 0:
        return "OK"
    parts = []
    for flag_val, flag_name in PROTECTION_FLAGS.items():
        if flags & flag_val:
            parts.append(flag_name)
    return ", ".join(parts) if parts else "OK"


def _decode_failure_flags(flags: int) -> str:
    """Decode failure flags to human-readable string."""
    if flags == 0:
        return "OK"
    return f"Error: 0x{flags:08X}"


def _parse_status_response(data: bytes) -> dict[str, Any]:
    """Parse status response from the BMS.

    Offsets are based on the raw BLE notification data (verified against
    the working ESPHome YAML configuration). All multi-byte values are
    little-endian.
    """
    if len(data) < MIN_RESPONSE_LENGTH:
        raise ValueError(
            f"Response too short: {len(data)} bytes, expected >= {MIN_RESPONSE_LENGTH}"
        )

    result: dict[str, Any] = {}

    # Total voltage (bytes 12-15, uint32_le, mV -> V)
    total_voltage = struct.unpack_from("<I", data, 12)[0] / 1000.0
    result["total_voltage"] = total_voltage

    # Individual cell voltages (bytes 16-47, 16x uint16_le, mV -> V)
    min_cell = 99.0
    max_cell = 0.0
    cell_count = 0
    cell_voltages: list[float | None] = [None] * MAX_CELLS

    for i in range(MAX_CELLS):
        raw = struct.unpack_from("<H", data, 16 + i * 2)[0]
        if raw == 0:
            continue
        cell_v = raw / 1000.0
        cell_voltages[i] = cell_v
        cell_count += 1
        if cell_v < min_cell:
            min_cell = cell_v
        if cell_v > max_cell:
            max_cell = cell_v

    result["cell_voltages"] = cell_voltages

    if cell_count > 0:
        result["min_cell_voltage"] = min_cell
        result["max_cell_voltage"] = max_cell
        result["delta_cell_voltage"] = round(max_cell - min_cell, 3)
    else:
        result["min_cell_voltage"] = None
        result["max_cell_voltage"] = None
        result["delta_cell_voltage"] = None

    # Current (bytes 48-51, int32_le, mA -> A)
    current = struct.unpack_from("<i", data, 48)[0] / 1000.0
    result["current"] = current

    # Power (calculated)
    result["power"] = round(total_voltage * current, 1)

    # Cell temperature (bytes 52-53, int16_le, degrees C)
    result["cell_temperature"] = struct.unpack_from("<h", data, 52)[0]

    # MOSFET temperature (bytes 54-55, int16_le, degrees C)
    result["mosfet_temperature"] = struct.unpack_from("<h", data, 54)[0]

    # Remaining capacity (bytes 62-63, uint16_le, x0.01 Ah -> Ah)
    result["remaining_capacity"] = struct.unpack_from("<H", data, 62)[0] / 100.0

    # Full charge capacity (bytes 64-65, uint16_le, x0.01 Ah -> Ah)
    result["full_charge_capacity"] = struct.unpack_from("<H", data, 64)[0] / 100.0

    # Heat state (bytes 68-71, uint32_le) - bit 0x80 = discharge disabled
    heat_state = struct.unpack_from("<I", data, 68)[0]
    result["discharge_enabled"] = not bool(heat_state & 0x00000080)

    # Protection state (bytes 76-79, uint32_le)
    protection_flags = struct.unpack_from("<I", data, 76)[0]
    result["protection_status"] = _decode_protection_flags(protection_flags)

    # Failure state (bytes 80-83, uint32_le)
    failure_flags = struct.unpack_from("<I", data, 80)[0]
    result["failure_status"] = _decode_failure_flags(failure_flags)

    # Balancing state (bytes 84-87, uint32_le)
    balancing_state = struct.unpack_from("<I", data, 84)[0]
    result["balancing"] = balancing_state != 0

    # Battery state (bytes 88-89, uint16_le)
    battery_state = struct.unpack_from("<H", data, 88)[0]
    result["charging"] = battery_state == BATTERY_STATE_CHARGING
    result["discharging"] = (
        battery_state == BATTERY_STATE_DISCHARGING and current < 0
    )
    result["charge_enabled"] = battery_state != BATTERY_STATE_CHARGE_DISABLED

    # SOC (bytes 90-91, uint16_le, %)
    result["state_of_charge"] = struct.unpack_from("<H", data, 90)[0]

    # SOH (bytes 92-93, uint16_le, %)
    result["state_of_health"] = struct.unpack_from("<H", data, 92)[0]

    # Discharge cycle count (bytes 96-99, uint32_le)
    result["discharge_cycles"] = struct.unpack_from("<I", data, 96)[0]

    # Total discharge Ah (bytes 100-103, uint32_le, mAh -> Ah)
    result["total_discharge_ah"] = struct.unpack_from("<I", data, 100)[0] / 1000.0

    result["online"] = True

    return result


class LitimeBmsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for LiTime BMS BLE data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"LiTime BMS {name}",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.address = address
        self._device_name = name
        self._client: BleakClient | None = None
        self._write_char: BleakGATTCharacteristic | None = None
        self._notify_char: BleakGATTCharacteristic | None = None
        self._response_buffer = bytearray()
        self._response_data: bytes | None = None
        self._response_event = asyncio.Event()
        self._missed_updates = 0
        self._connected = False
        self._connection_enabled = True

    @property
    def device_name(self) -> str:
        """Return the device name."""
        return self._device_name

    @property
    def connection_enabled(self) -> bool:
        """Return whether the connection is enabled."""
        return self._connection_enabled

    def _notification_handler(
        self, characteristic: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle BLE notification data."""
        _LOGGER.debug(
            "Notification: %d bytes, hex=%s",
            len(data),
            data.hex(),
        )

        # Check for response marker at byte[2] == 0x65
        if len(data) > RESPONSE_MARKER_OFFSET and data[RESPONSE_MARKER_OFFSET] == RESPONSE_MARKER_VALUE:
            # This is a status response - could arrive in one packet or fragmented
            self._response_buffer = bytearray(data)
        else:
            # Continuation fragment or non-status packet
            if len(self._response_buffer) > 0:
                self._response_buffer.extend(data)
            else:
                _LOGGER.debug("Ignoring non-status notification (%d bytes)", len(data))
                return

        if len(self._response_buffer) >= MIN_RESPONSE_LENGTH:
            _LOGGER.debug(
                "Complete response: %d bytes", len(self._response_buffer)
            )
            self._response_data = bytes(self._response_buffer)
            self._response_buffer.clear()
            self._response_event.set()
        else:
            _LOGGER.debug(
                "Buffered %d/%d bytes",
                len(self._response_buffer),
                MIN_RESPONSE_LENGTH,
            )

    async def _ensure_connected(self) -> bool:
        """Ensure BLE connection is established."""
        if self._client and self._client.is_connected:
            return True

        try:
            device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if device is None:
                _LOGGER.debug("Device %s not available", self.address)
                return False

            self._client = await establish_connection(
                BleakClient,
                device,
                self.address,
                max_attempts=3,
            )

            # Log all services and characteristics for debugging
            notify_char = None
            write_char = None

            for service in self._client.services:
                _LOGGER.debug("Service: %s", service.uuid)
                for char in service.characteristics:
                    props = char.properties
                    _LOGGER.debug("  Char: %s properties=%s", char.uuid, props)

                    if service.uuid.lower() == SERVICE_UUID:
                        if "notify" in props and char.uuid.lower() == NOTIFY_CHAR_UUID:
                            notify_char = char
                        if "write-without-response" in props or "write" in props:
                            if char.uuid.lower() == WRITE_CHAR_UUID:
                                write_char = char
                            elif char.uuid.lower() == NOTIFY_CHAR_UUID and write_char is None:
                                write_char = char

            # Subscribe to notifications on FFE1
            if notify_char is not None:
                await self._client.start_notify(
                    notify_char, self._notification_handler
                )
                self._notify_char = notify_char
                _LOGGER.info("Subscribed to notifications on %s", notify_char.uuid)
            else:
                _LOGGER.error("Notify characteristic (FFE1) not found")
                await self._client.disconnect()
                self._client = None
                return False

            # Use write characteristic (prefer FFE2, fallback FFE1)
            if write_char is not None:
                self._write_char = write_char
                _LOGGER.info("Using write characteristic %s", write_char.uuid)
            else:
                _LOGGER.error("No writable characteristic found")
                await self._client.disconnect()
                self._client = None
                return False

            self._connected = True
            self._missed_updates = 0
            _LOGGER.info("Connected to LiTime BMS %s", self.address)
            return True

        except (BleakError, TimeoutError, OSError) as err:
            _LOGGER.warning("Failed to connect to %s: %s", self.address, err)
            self._client = None
            self._write_char = None
            self._notify_char = None
            self._connected = False
            return False

    async def _send_command(self, cmd: int) -> None:
        """Send a command to the BMS."""
        if self._client is None or self._write_char is None:
            _LOGGER.warning("Cannot send command, not connected")
            return

        frame = _build_command(cmd)
        _LOGGER.debug(
            "Sending command 0x%02X to %s (%d bytes, hex=%s)",
            cmd,
            self._write_char.uuid,
            len(frame),
            frame.hex(),
        )
        try:
            await self._client.write_gatt_char(
                self._write_char, frame, response=False
            )
        except (BleakError, TimeoutError, OSError) as err:
            _LOGGER.warning("Failed to send command 0x%02X: %s", cmd, err)
            raise

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the BMS."""
        if not self._connection_enabled:
            return self._offline_data()

        if not await self._ensure_connected():
            self._missed_updates += 1
            _LOGGER.debug(
                "Cannot connect to %s (missed %d/%d)",
                self.address,
                self._missed_updates,
                MAX_MISSED_UPDATES,
            )
            return self._offline_data()

        # Reset event, buffer and send status query
        self._response_event.clear()
        self._response_data = None
        self._response_buffer.clear()

        try:
            await self._send_command(CMD_QUERY_STATUS)
        except (BleakError, TimeoutError, OSError) as err:
            _LOGGER.warning("Failed to send query to %s: %s", self.address, err)
            self._missed_updates += 1
            self._connected = False
            self._client = None
            self._write_char = None
            self._notify_char = None
            return self._offline_data()

        # Wait for response with timeout
        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=10.0)
        except TimeoutError:
            _LOGGER.warning(
                "Timeout waiting for response from %s (buffer has %d bytes)",
                self.address,
                len(self._response_buffer),
            )
            self._missed_updates += 1
            return self._offline_data()

        if self._response_data is None:
            _LOGGER.warning("No response data received from %s", self.address)
            return self._offline_data()

        try:
            result = _parse_status_response(self._response_data)
            self._missed_updates = 0
            return result
        except (ValueError, struct.error) as err:
            _LOGGER.warning("Failed to parse response from %s: %s", self.address, err)
            return self._offline_data()

    def _offline_data(self) -> dict[str, Any]:
        """Return offline data with all values set to None."""
        return {
            "online": False,
            "total_voltage": None,
            "current": None,
            "power": None,
            "state_of_charge": None,
            "state_of_health": None,
            "cell_temperature": None,
            "mosfet_temperature": None,
            "remaining_capacity": None,
            "full_charge_capacity": None,
            "discharge_cycles": None,
            "total_discharge_ah": None,
            "min_cell_voltage": None,
            "max_cell_voltage": None,
            "delta_cell_voltage": None,
            "cell_voltages": [None] * MAX_CELLS,
            "charging": None,
            "discharging": None,
            "balancing": None,
            "charge_enabled": None,
            "discharge_enabled": None,
            "protection_status": None,
            "failure_status": None,
        }

    async def async_set_charging(self, enabled: bool) -> None:
        """Enable or disable charging."""
        _LOGGER.info("Setting charging %s", "ON" if enabled else "OFF")
        if not await self._ensure_connected():
            _LOGGER.warning("Cannot set charging, not connected")
            return
        cmd = CMD_CHARGE_ON if enabled else CMD_CHARGE_OFF
        await self._send_command(cmd)
        await self.async_request_refresh()

    async def async_set_discharging(self, enabled: bool) -> None:
        """Enable or disable discharging."""
        _LOGGER.info("Setting discharging %s", "ON" if enabled else "OFF")
        if not await self._ensure_connected():
            _LOGGER.warning("Cannot set discharging, not connected")
            return
        cmd = CMD_DISCHARGE_ON if enabled else CMD_DISCHARGE_OFF
        await self._send_command(cmd)
        await self.async_request_refresh()

    async def async_set_connection_enabled(self, enabled: bool) -> None:
        """Enable or disable the BLE connection."""
        self._connection_enabled = enabled
        if enabled:
            _LOGGER.info("Connection enabled for %s, reconnecting", self.address)
            self._missed_updates = 0
            await self.async_request_refresh()
        else:
            _LOGGER.info("Connection disabled for %s, disconnecting", self.address)
            await self.async_disconnect()
            self.async_set_updated_data(self._offline_data())

    async def async_disconnect(self) -> None:
        """Disconnect from the BMS."""
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
            except (BleakError, TimeoutError, OSError):
                pass
        self._client = None
        self._write_char = None
        self._notify_char = None
        self._connected = False
