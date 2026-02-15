"""Config flow for LiTime BMS BLE integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_DEVICE_ADDRESS, CONF_DEVICE_NAME, DEVICE_NAME_PREFIXES, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LitimeBmsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LiTime BMS BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, str] = {}
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a device discovered via Bluetooth."""
        _LOGGER.debug(
            "Discovered BLE device: %s (%s)",
            discovery_info.name,
            discovery_info.address,
        )
        await self.async_set_unique_id(discovery_info.address.upper())
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery of a LiTime BMS device."""
        assert self._discovery_info is not None
        title = self._discovery_info.name or self._discovery_info.address

        if user_input is not None:
            return self.async_create_entry(
                title=title,
                data={
                    CONF_DEVICE_ADDRESS: self._discovery_info.address,
                    CONF_DEVICE_NAME: title,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": title},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_DEVICE_ADDRESS]
            await self.async_set_unique_id(address.upper(), raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices[address],
                data={
                    CONF_DEVICE_ADDRESS: address,
                    CONF_DEVICE_NAME: self._discovered_devices[address],
                },
            )

        current_addresses = self._async_current_ids()
        for info in async_discovered_service_info(self.hass, False):
            address = info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            if info.name and any(
                info.name.startswith(prefix) for prefix in DEVICE_NAME_PREFIXES
            ):
                self._discovered_devices[address] = info.name

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ADDRESS): vol.In(self._discovered_devices),
                }
            ),
        )
