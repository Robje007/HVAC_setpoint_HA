"""Number platform for HVAC Setpoint Curve thresholds."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HvacSetpointConfigEntry
from .const import (
    CONF_COOLING_CLIMATE,
    CONF_COOLING_NIGHT_OFFSET,
    CONF_COOLING_OFF_THRESHOLD,
    CONF_COOLING_ON_THRESHOLD,
    CONF_HEATING_CLIMATE,
    CONF_HEATING_NIGHT_OFFSET,
    CONF_HEATING_OFF_THRESHOLD,
    CONF_HEATING_ON_THRESHOLD,
    CONF_SENSOR_ONLY,
    DEFAULT_COOLING_OFF_THRESHOLD,
    DEFAULT_COOLING_NIGHT_OFFSET,
    DEFAULT_COOLING_ON_THRESHOLD,
    DEFAULT_HEATING_OFF_THRESHOLD,
    DEFAULT_HEATING_NIGHT_OFFSET,
    DEFAULT_HEATING_ON_THRESHOLD,
    DOMAIN,
    THRESHOLD_MAX,
    THRESHOLD_MIN,
)
from .entity import HvacSetpointEntity
from .validation import threshold_error

_ERROR_MESSAGES = {
    "invalid_cooling_hysteresis": "Cooling on temperature must be higher than cooling off temperature",
    "invalid_heating_hysteresis": "Heating off temperature must be higher than heating on temperature",
    "overlapping_heating_cooling": "Heating off temperature must be lower than cooling on temperature",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HvacSetpointConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up threshold number entities."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    options = coordinator.merged_options
    entities = []
    if options.get(CONF_COOLING_CLIMATE) or options.get(CONF_SENSOR_ONLY):
        entities.extend(
            [
                ThresholdNumber(coordinator, CONF_COOLING_ON_THRESHOLD, DEFAULT_COOLING_ON_THRESHOLD),
                ThresholdNumber(
                    coordinator,
                    CONF_COOLING_OFF_THRESHOLD,
                    DEFAULT_COOLING_OFF_THRESHOLD,
                ),
                NightOffsetNumber(
                    coordinator,
                    CONF_COOLING_NIGHT_OFFSET,
                    DEFAULT_COOLING_NIGHT_OFFSET,
                    direction=1,
                ),
            ]
        )
    if options.get(CONF_HEATING_CLIMATE) or options.get(CONF_SENSOR_ONLY):
        entities.extend(
            [
                ThresholdNumber(coordinator, CONF_HEATING_ON_THRESHOLD, DEFAULT_HEATING_ON_THRESHOLD),
                ThresholdNumber(
                    coordinator,
                    CONF_HEATING_OFF_THRESHOLD,
                    DEFAULT_HEATING_OFF_THRESHOLD,
                ),
                NightOffsetNumber(
                    coordinator,
                    CONF_HEATING_NIGHT_OFFSET,
                    DEFAULT_HEATING_NIGHT_OFFSET,
                    direction=-1,
                ),
            ]
        )
    async_add_entities(entities)


class ThresholdNumber(HvacSetpointEntity, NumberEntity):
    """Live-editable threshold number."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = THRESHOLD_MIN
    _attr_native_max_value = THRESHOLD_MAX
    _attr_native_step = 0.1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, key: str, default: float) -> None:
        """Initialize the number."""

        super().__init__(coordinator, key)
        self._key = key
        self._default = default
        self._attr_translation_key = key

    @property
    def native_value(self) -> float:
        """Return the configured threshold."""

        return float(self.coordinator.merged_options.get(self._key, self._default))

    async def async_set_native_value(self, value: float) -> None:
        """Persist a threshold change to config entry options."""

        candidate = {**self.coordinator.merged_options, self._key: round(float(value), 1)}
        error = threshold_error(
            candidate,
            cooling_enabled=bool(candidate.get(CONF_COOLING_CLIMATE) or candidate.get(CONF_SENSOR_ONLY)),
            heating_enabled=bool(candidate.get(CONF_HEATING_CLIMATE) or candidate.get(CONF_SENSOR_ONLY)),
        )
        if error:
            raise HomeAssistantError(_ERROR_MESSAGES[error])

        new_options = {**self.coordinator.config_entry.options, self._key: candidate[self._key]}
        self.coordinator.hass.config_entries.async_update_entry(
            self.coordinator.config_entry,
            options=new_options,
        )
        await self.coordinator.async_request_refresh()


class NightOffsetNumber(HvacSetpointEntity, NumberEntity):
    """Configure how far night mode moves a mode's target."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 0.0
    _attr_native_max_value = 5.0
    _attr_native_step = 0.1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:weather-night"

    def __init__(self, coordinator, key: str, default: float, *, direction: int) -> None:
        """Initialize a positive, user-facing night adjustment."""

        super().__init__(coordinator, key)
        self._key = key
        self._default = default
        self._direction = direction
        self._attr_translation_key = key

    @property
    def native_value(self) -> float:
        """Return the adjustment as a positive amount."""

        configured = float(self.coordinator.merged_options.get(self._key, self._default))
        return round(abs(configured), 1)

    async def async_set_native_value(self, value: float) -> None:
        """Persist the adjustment using its internal heating/cooling direction."""

        configured = round(abs(float(value)) * self._direction, 1)
        new_options = {**self.coordinator.config_entry.options, self._key: configured}
        self.coordinator.hass.config_entries.async_update_entry(
            self.coordinator.config_entry,
            options=new_options,
        )
        await self.coordinator.async_request_refresh()
