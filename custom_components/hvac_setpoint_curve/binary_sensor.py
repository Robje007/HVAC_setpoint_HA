"""Binary sensor platform for HVAC Setpoint Curve."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HvacSetpointConfigEntry
from .const import (
    CONF_COOLING_CLIMATE,
    CONF_COOLING_OFF_THRESHOLD,
    CONF_COOLING_ON_THRESHOLD,
    CONF_HEATING_CLIMATE,
    CONF_HEATING_OFF_THRESHOLD,
    CONF_HEATING_ON_THRESHOLD,
    CONF_SENSOR_ONLY,
    DEFAULT_COOLING_OFF_THRESHOLD,
    DEFAULT_COOLING_ON_THRESHOLD,
    DEFAULT_HEATING_OFF_THRESHOLD,
    DEFAULT_HEATING_ON_THRESHOLD,
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
    """Binary sensor exposing a hysteresis state."""

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
    def translation_placeholders(self) -> dict[str, str]:
        """Return the current hysteresis thresholds for the translated name."""

        options = self.coordinator.merged_options
        if self._attr_translation_key == "heating_active":
            on_threshold = options.get(CONF_HEATING_ON_THRESHOLD, DEFAULT_HEATING_ON_THRESHOLD)
            off_threshold = options.get(CONF_HEATING_OFF_THRESHOLD, DEFAULT_HEATING_OFF_THRESHOLD)
        else:
            on_threshold = options.get(CONF_COOLING_ON_THRESHOLD, DEFAULT_COOLING_ON_THRESHOLD)
            off_threshold = options.get(CONF_COOLING_OFF_THRESHOLD, DEFAULT_COOLING_OFF_THRESHOLD)
        return {
            "on_threshold": f"{float(on_threshold):.1f}",
            "off_threshold": f"{float(off_threshold):.1f}",
        }

    @property
    def is_on(self) -> bool | None:
        """Return whether this mode should be active."""

        if self.coordinator.data is None:
            return None
        return self._value_fn(self.coordinator.data)
