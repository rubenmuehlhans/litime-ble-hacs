"""The LiTime BMS BLE integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_ADDRESS, CONF_DEVICE_NAME, DOMAIN
from .coordinator import LitimeBmsCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LiTime BMS BLE from a config entry."""
    address: str = entry.data[CONF_DEVICE_ADDRESS]
    name: str = entry.data.get(CONF_DEVICE_NAME, address)

    coordinator = LitimeBmsCoordinator(hass, address, name)

    # BLE devices may not be reachable at startup. Set up the integration
    # immediately and let the coordinator retry in the background.
    # Do NOT use async_config_entry_first_refresh() as it raises
    # ConfigEntryNotReady on failure, blocking the entire setup.
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Schedule the first refresh in the background - will retry on its
    # update_interval if the device is not reachable yet.
    await coordinator.async_request_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: LitimeBmsCoordinator = entry.runtime_data
        await coordinator.async_disconnect()

    return unload_ok
