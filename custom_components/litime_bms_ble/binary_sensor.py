"""Binary sensor platform for LiTime BMS BLE."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LitimeBmsCoordinator


@dataclass(frozen=True, kw_only=True)
class LitimeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description of a LiTime binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[LitimeBinarySensorEntityDescription, ...] = (
    LitimeBinarySensorEntityDescription(
        key="charging",
        translation_key="charging",
        icon="mdi:battery-charging",
        value_fn=lambda data: data.get("charging"),
    ),
    LitimeBinarySensorEntityDescription(
        key="discharging",
        translation_key="discharging",
        icon="mdi:battery-arrow-down-outline",
        value_fn=lambda data: data.get("discharging"),
    ),
    LitimeBinarySensorEntityDescription(
        key="balancing",
        translation_key="balancing",
        icon="mdi:battery-sync",
        value_fn=lambda data: data.get("balancing"),
    ),
    LitimeBinarySensorEntityDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: data.get("online"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LiTime BMS binary sensors."""
    coordinator: LitimeBmsCoordinator = entry.runtime_data

    async_add_entities(
        LitimeBinarySensorEntity(coordinator, description, entry)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class LitimeBinarySensorEntity(
    CoordinatorEntity[LitimeBmsCoordinator], BinarySensorEntity
):
    """Representation of a LiTime BMS binary sensor."""

    entity_description: LitimeBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LitimeBmsCoordinator,
        description: LitimeBinarySensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
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
        """Return the binary sensor state."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        # Online sensor is always available when coordinator is available
        if self.entity_description.key == "online":
            return True
        if self.coordinator.data is None:
            return False
        return self.coordinator.data.get("online", False)
