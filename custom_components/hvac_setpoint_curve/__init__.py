"""The HVAC Setpoint Curve integration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_COOLING_CURVE_POINTS,
    CONF_COOLING_PRESET,
    CONF_CURVE_POINTS,
    CONF_ENTRY_ID,
    CONF_HEATING_CURVE_POINTS,
    CONF_HEATING_PRESET,
    CONF_MODE,
    CONF_POINTS,
    CONF_PRESET,
    DEFAULT_HEATING_CURVE_POINTS,
    DEFAULT_PRESET,
    DOMAIN,
    MODE_BOTH,
    MODE_COOLING,
    MODE_HEATING,
    PLATFORMS,
    PRESET_CUSTOM,
    SERVICE_SET_CURVE,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import HvacSetpointCoordinator

    HvacSetpointConfigEntry = ConfigEntry[HvacSetpointCoordinator]
else:
    HvacSetpointConfigEntry = Any


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up integration-level services."""

    import voluptuous as vol
    from homeassistant.components.http import StaticPathConfig

    from .curve import parse_curve_points, serialize_curve_points

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                "/hvac_setpoint_curve/hvac-setpoint-curve-card.js",
                str(Path(__file__).parent / "www" / "hvac-setpoint-curve-card.js"),
                True,
            )
        ]
    )

    async def _async_set_curve(call: Any) -> None:
        entry_id = call.data[CONF_ENTRY_ID]
        mode = call.data[CONF_MODE]
        points = serialize_curve_points(parse_curve_points(call.data[CONF_POINTS]))

        entry = next(
            (item for item in hass.config_entries.async_entries(DOMAIN) if item.entry_id == entry_id),
            None,
        )
        if entry is None:
            raise ValueError(f"No HVAC Setpoint Curve entry found for entry_id {entry_id}")

        options = {**entry.options, CONF_PRESET: PRESET_CUSTOM}
        if mode in (MODE_COOLING, MODE_BOTH):
            options[CONF_CURVE_POINTS] = points
            options[CONF_COOLING_CURVE_POINTS] = points
            options[CONF_COOLING_PRESET] = PRESET_CUSTOM
        if mode in (MODE_HEATING, MODE_BOTH):
            options[CONF_HEATING_CURVE_POINTS] = points
            options[CONF_HEATING_PRESET] = PRESET_CUSTOM
        hass.config_entries.async_update_entry(entry, options=options)

        coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if coordinator is not None:
            await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CURVE,
        _async_set_curve,
        schema=vol.Schema(
            {
                vol.Required(CONF_ENTRY_ID): str,
                vol.Required(CONF_MODE): vol.In([MODE_COOLING, MODE_HEATING, MODE_BOTH]),
                vol.Required(CONF_POINTS): [
                    {
                        vol.Required("outdoor_temp"): vol.Coerce(float),
                        vol.Required("setpoint"): vol.Coerce(float),
                    }
                ],
            }
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HvacSetpointConfigEntry) -> bool:
    """Set up HVAC Setpoint Curve from a config entry."""

    from homeassistant.helpers import entity_registry as er

    from .coordinator import HvacSetpointCoordinator

    entity_registry = er.async_get(hass)
    for legacy_key in ("cooling_target_setpoint", "heating_target_setpoint"):
        entity_id = entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            f"{entry.entry_id}_{legacy_key}",
        )
        if entity_id is not None:
            entity_registry.async_remove(entity_id)

    legacy_preset_entity = entity_registry.async_get_entity_id(
        "select",
        DOMAIN,
        f"{entry.entry_id}_preset",
    )
    if legacy_preset_entity is not None:
        options = {**entry.data, **entry.options}
        replacement = "cooling_preset" if options.get("cooling_climate") else "heating_preset"
        entity_registry.async_update_entity(
            legacy_preset_entity,
            new_unique_id=f"{entry.entry_id}_{replacement}",
        )

    coordinator = HvacSetpointCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HvacSetpointConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: HvacSetpointConfigEntry) -> bool:
    """Migrate old entries."""

    old_version = entry.version
    data = dict(entry.data)
    options = dict(entry.options)

    if old_version < 2:
        curve_keys = (CONF_CURVE_POINTS, CONF_COOLING_CURVE_POINTS, CONF_HEATING_CURVE_POINTS)

        for values in (data, options):
            for key in curve_keys:
                points = values.get(key)
                if not isinstance(points, list) or len(points) != 2:
                    continue
                first, last = sorted(points, key=lambda point: float(point["outdoor_temp"]))
                midpoint = {
                    "outdoor_temp": round((float(first["outdoor_temp"]) + float(last["outdoor_temp"])) / 2, 1),
                    "setpoint": round((float(first["setpoint"]) + float(last["setpoint"])) / 2, 1),
                }
                values[key] = [first, midpoint, last]

    if old_version < 3 and options.get(CONF_PRESET, data.get(CONF_PRESET)) == PRESET_CUSTOM:
        shared_points = (
            options.get(CONF_CURVE_POINTS)
            or options.get(CONF_COOLING_CURVE_POINTS)
            or data.get(CONF_CURVE_POINTS)
            or data.get(CONF_COOLING_CURVE_POINTS)
            or data.get(CONF_HEATING_CURVE_POINTS)
        )
        if shared_points:
            options[CONF_CURVE_POINTS] = shared_points
            options[CONF_COOLING_CURVE_POINTS] = shared_points
            options[CONF_HEATING_CURVE_POINTS] = shared_points

    if old_version < 4:
        legacy_preset = options.get(CONF_PRESET, data.get(CONF_PRESET, PRESET_CUSTOM))
        heating_curve = options.get(CONF_HEATING_CURVE_POINTS, data.get(CONF_HEATING_CURVE_POINTS))
        heating_preset = DEFAULT_PRESET if heating_curve == DEFAULT_HEATING_CURVE_POINTS else PRESET_CUSTOM
        options.setdefault(CONF_COOLING_PRESET, legacy_preset)
        options.setdefault(CONF_HEATING_PRESET, heating_preset)
        hass.config_entries.async_update_entry(entry, data=data, options=options, version=4)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: HvacSetpointConfigEntry) -> None:
    """Reload after options are changed."""

    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator is not None:
        coordinator.refresh_listeners()
        await coordinator.async_request_refresh()
    await hass.config_entries.async_reload(entry.entry_id)
