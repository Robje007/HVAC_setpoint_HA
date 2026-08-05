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
    ATTR_COOLING_CURVE_SETPOINT,
    ATTR_COOLING_CURVE_POINTS,
    ATTR_COOLING_INDOOR_TEMPERATURE_SOURCE,
    ATTR_COOLING_INDOOR_TEMPERATURE_USED,
    ATTR_COOLING_PRESET,
    ATTR_COOLING_STABILIZING,
    ATTR_CURVE_POINTS,
    ATTR_HEATING_CURVE_POINTS,
    ATTR_HEATING_CURVE_SETPOINT,
    ATTR_HEATING_INDOOR_TEMPERATURE_SOURCE,
    ATTR_HEATING_INDOOR_TEMPERATURE_USED,
    ATTR_HEATING_PRESET,
    ATTR_HEATING_STABILIZING,
    ATTR_HUMIDITY_USED,
    ATTR_NIGHT_MODE,
    ATTR_OUTDOOR_TEMPERATURE_AVERAGE,
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
            ATTR_OUTDOOR_TEMPERATURE_AVERAGE: data.outdoor_temperature_average if data else None,
            ATTR_HUMIDITY_USED: data.humidity_used if data else None,
            ATTR_NIGHT_MODE: data.night_mode if data else False,
            ATTR_COOLING_CURVE_SETPOINT: data.cooling_curve_setpoint if data else None,
            ATTR_HEATING_CURVE_SETPOINT: data.heating_curve_setpoint if data else None,
            ATTR_COOLING_INDOOR_TEMPERATURE_USED: data.cooling_indoor_temperature_used if data else None,
            ATTR_HEATING_INDOOR_TEMPERATURE_USED: data.heating_indoor_temperature_used if data else None,
            ATTR_COOLING_INDOOR_TEMPERATURE_SOURCE: data.cooling_indoor_temperature_source if data else None,
            ATTR_HEATING_INDOOR_TEMPERATURE_SOURCE: data.heating_indoor_temperature_source if data else None,
            ATTR_COOLING_STABILIZING: data.cooling_stabilizing if data else False,
            ATTR_HEATING_STABILIZING: data.heating_stabilizing if data else False,
            ATTR_ACTIVE_PRESET: data.active_preset if data else None,
            ATTR_COOLING_PRESET: data.cooling_preset if data else None,
            ATTR_HEATING_PRESET: data.heating_preset if data else None,
            ATTR_CONFIG_ENTRY_ID: self.coordinator.config_entry.entry_id,
            ATTR_CURVE_POINTS: options.get(CONF_CURVE_POINTS, DEFAULT_CURVE_POINTS),
            ATTR_COOLING_CURVE_POINTS: options.get(CONF_COOLING_CURVE_POINTS, DEFAULT_COOLING_CURVE_POINTS),
            ATTR_HEATING_CURVE_POINTS: options.get(CONF_HEATING_CURVE_POINTS, DEFAULT_HEATING_CURVE_POINTS),
            "cooling_enabled": bool(options.get(CONF_COOLING_CLIMATE) or options.get(CONF_SENSOR_ONLY)),
            "heating_enabled": bool(options.get(CONF_HEATING_CLIMATE) or options.get(CONF_SENSOR_ONLY)),
        }
