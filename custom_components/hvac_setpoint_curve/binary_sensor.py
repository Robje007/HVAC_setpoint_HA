"""Binary sensor platform for HVAC Setpoint Curve."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HvacSetpointConfigEntry
from .const import (
    CONF_COOLING_CLIMATE,
    CONF_HEATING_CLIMATE,
    CONF_SENSOR_ONLY,
    DOMAIN,
)
from .coordinator import HvacCurveData
from .entity import HvacSetpointEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HvacSetpointConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    options = coordinator.merged_options
    entities = []
    if options.get(CONF_COOLING_CLIMATE) or options.get(CONF_SENSOR_ONLY):
        entities.append(HvacModeBinarySensor(coordinator, "cooling_active", lambda data: data.cooling_active))
    if options.get(CONF_HEATING_CLIMATE) or options.get(CONF_SENSOR_ONLY):
        entities.append(HvacModeBinarySensor(coordinator, "heating_active", lambda data: data.heating_active))
    async_add_entities(entities)


class HvacModeBinarySensor(HvacSetpointEntity, BinarySensorEntity):
    """Binary sensor exposing the current heating or cooling demand state."""

    def __init__(
        self,
        coordinator,
        key: str,
        value_fn: Callable[[HvacCurveData], bool],
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self._value_fn = value_fn

    @property
    def is_on(self) -> bool | None:
        """Return whether this mode should be active."""

        if self.coordinator.data is None:
            return None
        return self._value_fn(self.coordinator.data)
