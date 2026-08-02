"""Sensor platform for HVAC Setpoint Curve."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HvacSetpointConfigEntry
from .const import (
    ATTR_ACTIVE_PRESET,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_COOLING_CURVE_POINTS,
    ATTR_CURVE_POINTS,
    ATTR_HEATING_CURVE_POINTS,
    ATTR_HUMIDITY_USED,
    ATTR_OUTDOOR_TEMPERATURE_USED,
    CONF_COOLING_CLIMATE,
    CONF_COOLING_CURVE_POINTS,
    CONF_CURVE_POINTS,
    CONF_HEATING_CLIMATE,
    CONF_HEATING_CURVE_POINTS,
    CONF_SENSOR_ONLY,
    DEFAULT_COOLING_CURVE_POINTS,
    DEFAULT_CURVE_POINTS,
    DEFAULT_HEATING_CURVE_POINTS,
    DOMAIN,
)
from .entity import HvacSetpointEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HvacSetpointConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TargetSetpointSensor(coordinator, "target_setpoint", "target_setpoint")])


class TargetSetpointSensor(HvacSetpointEntity, SensorEntity):
    """Computed target setpoint sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, key: str, data_key: str) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self._data_key = data_key

    @property
    def native_value(self) -> float | None:
        """Return the current target setpoint."""

        return getattr(self.coordinator.data, self._data_key) if self.coordinator.data else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return diagnostic attributes."""

        data = self.coordinator.data
        options = self.coordinator.merged_options
        return {
            ATTR_OUTDOOR_TEMPERATURE_USED: data.outdoor_temperature_used if data else None,
            ATTR_HUMIDITY_USED: data.humidity_used if data else None,
            ATTR_ACTIVE_PRESET: data.active_preset if data else None,
            ATTR_CONFIG_ENTRY_ID: self.coordinator.config_entry.entry_id,
            ATTR_CURVE_POINTS: options.get(CONF_CURVE_POINTS, DEFAULT_CURVE_POINTS),
            ATTR_COOLING_CURVE_POINTS: options.get(CONF_COOLING_CURVE_POINTS, DEFAULT_COOLING_CURVE_POINTS),
            ATTR_HEATING_CURVE_POINTS: options.get(CONF_HEATING_CURVE_POINTS, DEFAULT_HEATING_CURVE_POINTS),
            "cooling_enabled": bool(options.get(CONF_COOLING_CLIMATE) or options.get(CONF_SENSOR_ONLY)),
            "heating_enabled": bool(options.get(CONF_HEATING_CLIMATE) or options.get(CONF_SENSOR_ONLY)),
        }
