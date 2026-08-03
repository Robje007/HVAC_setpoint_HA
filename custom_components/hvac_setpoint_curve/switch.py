"""Switch platform for enabling or disabling automatic HVAC control."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HvacSetpointConfigEntry
from .const import CONF_CONTROLLER_ENABLED, DEFAULT_CONTROLLER_ENABLED, DOMAIN
from .entity import HvacSetpointEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HvacSetpointConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the controller switch entity."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ControllerEnabledSwitch(coordinator)])


class ControllerEnabledSwitch(HvacSetpointEntity, SwitchEntity):
    """Allow users to pause automatic control without changing the curve."""

    _attr_translation_key = "controller_enabled"
    _attr_icon = "mdi:thermostat-auto"

    def __init__(self, coordinator) -> None:
        """Initialize the controller switch."""

        super().__init__(coordinator, "controller_enabled")

    @property
    def is_on(self) -> bool:
        """Return whether automatic HVAC control is enabled."""

        return bool(self.coordinator.merged_options.get(CONF_CONTROLLER_ENABLED, DEFAULT_CONTROLLER_ENABLED))

    async def async_turn_on(self, **kwargs) -> None:
        """Enable automatic HVAC control."""

        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable automatic HVAC control without changing linked equipment."""

        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        """Persist the controller state and refresh calculations."""

        new_options = {**self.coordinator.config_entry.options, CONF_CONTROLLER_ENABLED: enabled}
        self.coordinator.hass.config_entries.async_update_entry(
            self.coordinator.config_entry,
            options=new_options,
        )
        await self.coordinator.async_request_refresh()
