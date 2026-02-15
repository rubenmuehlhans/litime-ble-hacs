"""Sensor platform for LiTime BMS BLE."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MAX_CELLS
from .coordinator import LitimeBmsCoordinator

UNIT_AMPERE_HOURS = "Ah"


@dataclass(frozen=True, kw_only=True)
class LitimeSensorEntityDescription(SensorEntityDescription):
    """Description of a LiTime sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] = lambda data: None


SENSOR_DESCRIPTIONS: tuple[LitimeSensorEntityDescription, ...] = (
    LitimeSensorEntityDescription(
        key="total_voltage",
        translation_key="total_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: data.get("total_voltage"),
    ),
    LitimeSensorEntityDescription(
        key="current",
        translation_key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("current"),
    ),
    LitimeSensorEntityDescription(
        key="power",
        translation_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("power"),
    ),
    LitimeSensorEntityDescription(
        key="state_of_charge",
        translation_key="state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("state_of_charge"),
    ),
    LitimeSensorEntityDescription(
        key="state_of_health",
        translation_key="state_of_health",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:heart-pulse",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("state_of_health"),
    ),
    LitimeSensorEntityDescription(
        key="cell_temperature",
        translation_key="cell_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("cell_temperature"),
    ),
    LitimeSensorEntityDescription(
        key="mosfet_temperature",
        translation_key="mosfet_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("mosfet_temperature"),
    ),
    LitimeSensorEntityDescription(
        key="remaining_capacity",
        translation_key="remaining_capacity",
        native_unit_of_measurement=UNIT_AMPERE_HOURS,
        icon="mdi:battery-arrow-down",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("remaining_capacity"),
    ),
    LitimeSensorEntityDescription(
        key="full_charge_capacity",
        translation_key="full_charge_capacity",
        native_unit_of_measurement=UNIT_AMPERE_HOURS,
        icon="mdi:battery-arrow-up",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("full_charge_capacity"),
    ),
    LitimeSensorEntityDescription(
        key="discharge_cycles",
        translation_key="discharge_cycles",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("discharge_cycles"),
    ),
    LitimeSensorEntityDescription(
        key="total_discharge_ah",
        translation_key="total_discharge_ah",
        native_unit_of_measurement=UNIT_AMPERE_HOURS,
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("total_discharge_ah"),
    ),
    LitimeSensorEntityDescription(
        key="min_cell_voltage",
        translation_key="min_cell_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: data.get("min_cell_voltage"),
    ),
    LitimeSensorEntityDescription(
        key="max_cell_voltage",
        translation_key="max_cell_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: data.get("max_cell_voltage"),
    ),
    LitimeSensorEntityDescription(
        key="delta_cell_voltage",
        translation_key="delta_cell_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: data.get("delta_cell_voltage"),
    ),
    LitimeSensorEntityDescription(
        key="protection_status",
        translation_key="protection_status",
        icon="mdi:shield-alert",
        value_fn=lambda data: data.get("protection_status"),
    ),
    LitimeSensorEntityDescription(
        key="failure_status",
        translation_key="failure_status",
        icon="mdi:alert-circle",
        value_fn=lambda data: data.get("failure_status"),
    ),
    LitimeSensorEntityDescription(
        key="estimate_15_soc_time",
        translation_key="estimate_15_soc_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",
        value_fn=lambda data: data.get("estimate_15_soc_time"),
    ),
    LitimeSensorEntityDescription(
        key="remaining_time_hours",
        translation_key="remaining_time_hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:timer-outline",
        value_fn=lambda data: data.get("remaining_time_hours"),
    ),
)


def _make_cell_voltage_description(
    cell_index: int,
) -> LitimeSensorEntityDescription:
    """Create a sensor description for a cell voltage."""
    return LitimeSensorEntityDescription(
        key=f"cell_voltage_{cell_index + 1}",
        translation_key=f"cell_voltage_{cell_index + 1}",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data, idx=cell_index: (
            data.get("cell_voltages", [None] * MAX_CELLS)[idx]
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LiTime BMS sensors."""
    coordinator: LitimeBmsCoordinator = entry.runtime_data

    entities: list[LitimeSensorEntity] = []

    # Add all standard sensors
    for description in SENSOR_DESCRIPTIONS:
        entities.append(LitimeSensorEntity(coordinator, description, entry))

    # Add cell voltage sensors (only for cells that have data)
    for i in range(MAX_CELLS):
        description = _make_cell_voltage_description(i)
        entities.append(LitimeSensorEntity(coordinator, description, entry))

    async_add_entities(entities)


class LitimeSensorEntity(CoordinatorEntity[LitimeBmsCoordinator], SensorEntity):
    """Representation of a LiTime BMS sensor."""

    entity_description: LitimeSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LitimeBmsCoordinator,
        description: LitimeSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
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
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        if self.coordinator.data is None:
            return False
        return self.coordinator.data.get("online", False)
