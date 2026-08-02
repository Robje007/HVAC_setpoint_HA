"""Shared entity helpers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HvacSetpointCoordinator


class HvacSetpointEntity(CoordinatorEntity[HvacSetpointCoordinator]):
    """Base entity for HVAC Setpoint Curve."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HvacSetpointCoordinator, key: str) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.config_entry.title,
            manufacturer="HVAC Setpoint Curve",
            model="Weather compensated setpoint controller",
        )
