"""Switch platform for LiTime BMS BLE."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LitimeBmsCoordinator


@dataclass(frozen=True, kw_only=True)
class LitimeSwitchEntityDescription(SwitchEntityDescription):
    """Description of a LiTime switch entity."""

    value_fn: Callable[[dict[str, Any]], bool | None]
    turn_on_fn: Callable[[LitimeBmsCoordinator], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[LitimeBmsCoordinator], Coroutine[Any, Any, None]]


SWITCH_DESCRIPTIONS: tuple[LitimeSwitchEntityDescription, ...] = (
    LitimeSwitchEntityDescription(
        key="charging_switch",
        translation_key="charging_switch",
        icon="mdi:battery-charging",
        value_fn=lambda data: data.get("charge_enabled"),
        turn_on_fn=lambda coord: coord.async_set_charging(True),
        turn_off_fn=lambda coord: coord.async_set_charging(False),
    ),
    LitimeSwitchEntityDescription(
        key="discharging_switch",
        translation_key="discharging_switch",
        icon="mdi:battery-arrow-down-outline",
        value_fn=lambda data: data.get("discharge_enabled"),
        turn_on_fn=lambda coord: coord.async_set_discharging(True),
        turn_off_fn=lambda coord: coord.async_set_discharging(False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LiTime BMS switches."""
    coordinator: LitimeBmsCoordinator = entry.runtime_data

    entities: list[SwitchEntity] = [
        LitimeSwitchEntity(coordinator, description, entry)
        for description in SWITCH_DESCRIPTIONS
    ]
    entities.append(LitimeConnectionSwitch(coordinator, entry))

    async_add_entities(entities)


class LitimeSwitchEntity(CoordinatorEntity[LitimeBmsCoordinator], SwitchEntity):
    """Representation of a LiTime BMS switch."""

    entity_description: LitimeSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LitimeBmsCoordinator,
        description: LitimeSwitchEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.unique_id or entry.entry_id)},
            "name": coordinator.device_name,
            "manufacturer": "LiTime",
            "model": "LiFePO4 BMS",
            "connections": {("bluetooth", coordinator.address)},
        }

    @property
    def is_on(self) -> bool | None:
        """Return the switch state."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.turn_on_fn(self.coordinator)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.turn_off_fn(self.coordinator)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        if self.coordinator.data is None:
            return False
        return self.coordinator.data.get("online", False)


class LitimeConnectionSwitch(CoordinatorEntity[LitimeBmsCoordinator], SwitchEntity):
    """Switch to enable/disable the BLE connection."""

    _attr_has_entity_name = True
    _attr_translation_key = "connection"
    _attr_icon = "mdi:bluetooth-connect"

    def __init__(
        self,
        coordinator: LitimeBmsCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the connection switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_connection"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.unique_id or entry.entry_id)},
            "name": coordinator.device_name,
            "manufacturer": "LiTime",
            "model": "LiFePO4 BMS",
            "connections": {("bluetooth", coordinator.address)},
        }

    @property
    def is_on(self) -> bool:
        """Return True if the connection is enabled."""
        return self.coordinator.connection_enabled

    @property
    def available(self) -> bool:
        """Return True - connection switch is always available."""
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the BLE connection."""
        await self.coordinator.async_set_connection_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the BLE connection."""
        await self.coordinator.async_set_connection_enabled(False)
