"""Switch platform for enabling or disabling automatic HVAC control."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HvacSetpointConfigEntry
from .const import (
    CONF_CONTROLLER_ENABLED,
    CONF_NIGHT_MODE,
    DEFAULT_CONTROLLER_ENABLED,
    DEFAULT_NIGHT_MODE,
    DOMAIN,
)
from .entity import HvacSetpointEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HvacSetpointConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the controller switch entity."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ConfigOptionSwitch(
                coordinator,
                key="controller_enabled",
                option=CONF_CONTROLLER_ENABLED,
                default=DEFAULT_CONTROLLER_ENABLED,
                icon="mdi:thermostat-auto",
            ),
            ConfigOptionSwitch(
                coordinator,
                key="night_mode",
                option=CONF_NIGHT_MODE,
                default=DEFAULT_NIGHT_MODE,
                icon="mdi:weather-night",
            ),
        ]
    )


class ConfigOptionSwitch(HvacSetpointEntity, SwitchEntity):
    """Expose a persistent boolean integration option."""

    def __init__(self, coordinator, *, key: str, option: str, default: bool, icon: str) -> None:
        """Initialize an option-backed switch."""

        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self._attr_icon = icon
        self._option = option
        self._default = default

    @property
    def is_on(self) -> bool:
        """Return whether automatic HVAC control is enabled."""

        return bool(self.coordinator.merged_options.get(self._option, self._default))

    async def async_turn_on(self, **kwargs) -> None:
        """Enable automatic HVAC control."""

        await self._async_set_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable automatic HVAC control without changing linked equipment."""

        await self._async_set_state(False)

    async def _async_set_state(self, enabled: bool) -> None:
        """Persist the switch state and refresh calculations."""

        new_options = {**self.coordinator.config_entry.options, self._option: enabled}
        self.coordinator.hass.config_entries.async_update_entry(
            self.coordinator.config_entry,
            options=new_options,
        )
        await self.coordinator.async_request_refresh()
