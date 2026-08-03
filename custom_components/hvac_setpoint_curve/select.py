"""Select platform for independent HVAC Setpoint Curve presets."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HvacSetpointConfigEntry
from .const import (
    CONF_COOLING_CLIMATE,
    CONF_COOLING_CURVE_POINTS,
    CONF_COOLING_PRESET,
    CONF_HEATING_CLIMATE,
    CONF_HEATING_CURVE_POINTS,
    CONF_HEATING_PRESET,
    CONF_PRESET,
    CONF_SENSOR_ONLY,
    DOMAIN,
    PRESET_CUSTOM,
    PRESETS,
    preset_curve,
    preset_name,
)
from .entity import HvacSetpointEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HvacSetpointConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one preset select per available operating mode."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    options = coordinator.merged_options
    entities: list[ModePresetSelect] = []
    if options.get(CONF_COOLING_CLIMATE) or options.get(CONF_SENSOR_ONLY):
        entities.append(
            ModePresetSelect(
                coordinator,
                "cooling_preset",
                CONF_COOLING_PRESET,
                CONF_COOLING_CURVE_POINTS,
                "cooling",
                allow_aggressive=True,
            )
        )
    if options.get(CONF_HEATING_CLIMATE) or options.get(CONF_SENSOR_ONLY):
        entities.append(
            ModePresetSelect(
                coordinator,
                "heating_preset",
                CONF_HEATING_PRESET,
                CONF_HEATING_CURVE_POINTS,
                "heating",
                allow_aggressive=False,
            )
        )
    async_add_entities(entities)


class ModePresetSelect(HvacSetpointEntity, SelectEntity):
    """Select entity that applies a preset to one operating mode only."""

    def __init__(
        self,
        coordinator,
        key: str,
        preset_key: str,
        curve_key: str,
        mode: str,
        *,
        allow_aggressive: bool,
    ) -> None:
        """Initialize a mode-specific preset select."""

        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self._preset_key = preset_key
        self._curve_key = curve_key
        self._mode = mode
        language = coordinator.hass.config.language
        self._preset_names = {
            preset: preset_name(preset, language)
            for preset in PRESETS
            if allow_aggressive or preset != "rail_aggressive_cooling"
        }
        self._custom_name = preset_name(PRESET_CUSTOM, language)
        self._attr_options = [*self._preset_names.values(), self._custom_name]

    @property
    def current_option(self) -> str | None:
        """Return the current mode-specific preset label."""

        preset = self.coordinator.merged_options.get(
            self._preset_key,
            self.coordinator.merged_options.get(CONF_PRESET, PRESET_CUSTOM),
        )
        return self._preset_names.get(preset, self._custom_name)

    async def async_select_option(self, option: str) -> None:
        """Apply a preset to this mode without changing the other mode."""

        preset = next(
            (key for key, name in self._preset_names.items() if name == option),
            PRESET_CUSTOM,
        )
        new_options = {
            **self.coordinator.config_entry.options,
            self._preset_key: preset,
            CONF_PRESET: PRESET_CUSTOM,
        }
        if preset in PRESETS:
            new_options[self._curve_key] = preset_curve(preset, self._mode)
        self.coordinator.hass.config_entries.async_update_entry(
            self.coordinator.config_entry,
            options=new_options,
        )
        await self.coordinator.async_request_refresh()
