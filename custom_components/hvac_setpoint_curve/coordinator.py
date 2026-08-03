"""Coordinator and control logic for HVAC Setpoint Curve."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from homeassistant.components.climate import ATTR_HVAC_MODE, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_COOLING_CLIMATE,
    CONF_COOLING_CURVE_POINTS,
    CONF_COOLING_OFF_THRESHOLD,
    CONF_COOLING_ON_THRESHOLD,
    CONF_CURVE_POINTS,
    CONF_HEATING_CLIMATE,
    CONF_HEATING_CURVE_POINTS,
    CONF_HEATING_OFF_THRESHOLD,
    CONF_HEATING_ON_THRESHOLD,
    CONF_HUMIDITY_SENSOR,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_PRESET,
    CONF_SENSOR_ONLY,
    CONF_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE,
    DEFAULT_COOLING_CURVE_POINTS,
    DEFAULT_COOLING_OFF_THRESHOLD,
    DEFAULT_COOLING_ON_THRESHOLD,
    DEFAULT_HEATING_CURVE_POINTS,
    DEFAULT_HEATING_OFF_THRESHOLD,
    DEFAULT_HEATING_ON_THRESHOLD,
    DEFAULT_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE,
    DOMAIN,
)
from .curve import computed_setpoint
from .hysteresis import decide_cooling, decide_heating
from .validation import threshold_error

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_HVAC_MODE = "set_hvac_mode"
SERVICE_SET_TEMPERATURE = "set_temperature"

ATTR_MIN_TEMP = "min_temp"
ATTR_MAX_TEMP = "max_temp"
ATTR_TARGET_TEMP_STEP = "target_temp_step"


@dataclass(slots=True)
class HvacCurveData:
    """Computed integration state."""

    target_setpoint: float | None = None
    cooling_target_setpoint: float | None = None
    heating_target_setpoint: float | None = None
    outdoor_temperature_used: float | None = None
    humidity_used: float | None = None
    active_preset: str | None = None
    cooling_active: bool = False
    heating_active: bool = False


class HvacSetpointCoordinator(DataUpdateCoordinator[HvacCurveData]):
    """Coordinate setpoint calculation and optional climate control."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""

        self._unsub_state_change: Any = None
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=5),
            config_entry=entry,
        )

    async def async_config_entry_first_refresh(self) -> None:
        """Refresh immediately, then subscribe to relevant entity changes."""

        await super().async_config_entry_first_refresh()
        self._subscribe_state_changes()

    async def async_shutdown(self) -> None:
        """Clean up listeners."""

        if self._unsub_state_change is not None:
            self._unsub_state_change()
            self._unsub_state_change = None

    @property
    def merged_options(self) -> dict[str, Any]:
        """Return entry data and live options merged together."""

        return {**self.config_entry.data, **self.config_entry.options}

    async def _async_update_data(self) -> HvacCurveData:
        """Recompute data and run optional control actions."""

        options = self.merged_options
        previous = self.data or HvacCurveData()
        outdoor_temp = self._get_outdoor_temperature(options)
        humidity = self._get_float_state(options.get(CONF_HUMIDITY_SENSOR))

        if outdoor_temp is None:
            _LOGGER.warning("No usable outdoor temperature found for %s", self.config_entry.title)
            data = HvacCurveData(
                active_preset=options.get(CONF_PRESET),
                cooling_active=(
                    False
                    if options.get(
                        CONF_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE,
                        DEFAULT_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE,
                    )
                    else previous.cooling_active
                ),
                heating_active=(
                    False
                    if options.get(
                        CONF_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE,
                        DEFAULT_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE,
                    )
                    else previous.heating_active
                ),
            )
            if options.get(
                CONF_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE,
                DEFAULT_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE,
            ):
                await self._apply_control_states(options, data)
            else:
                _LOGGER.warning(
                    "Leaving linked HVAC unchanged for %s because the outdoor-temperature fail-safe is disabled",
                    self.config_entry.title,
                )
            return data

        cooling_target_setpoint = computed_setpoint(
            _curve_for_mode(options, CONF_COOLING_CURVE_POINTS, DEFAULT_COOLING_CURVE_POINTS),
            outdoor_temp,
            humidity,
        )
        heating_target_setpoint = computed_setpoint(
            _curve_for_mode(options, CONF_HEATING_CURVE_POINTS, DEFAULT_HEATING_CURVE_POINTS),
            outdoor_temp,
            humidity,
        )
        data = HvacCurveData(
            target_setpoint=cooling_target_setpoint,
            cooling_target_setpoint=cooling_target_setpoint,
            heating_target_setpoint=heating_target_setpoint,
            outdoor_temperature_used=outdoor_temp,
            humidity_used=humidity,
            active_preset=options.get(CONF_PRESET),
            cooling_active=previous.cooling_active,
            heating_active=previous.heating_active,
        )

        validation_error = threshold_error(
            options,
            cooling_enabled=bool(options.get(CONF_COOLING_CLIMATE) or options.get(CONF_SENSOR_ONLY)),
            heating_enabled=bool(options.get(CONF_HEATING_CLIMATE) or options.get(CONF_SENSOR_ONLY)),
        )
        if validation_error:
            _LOGGER.error("Not controlling HVAC for %s: %s", self.config_entry.title, validation_error)
            data.cooling_active = False
            data.heating_active = False
        else:
            data.cooling_active = self._cooling_active(options, outdoor_temp, previous.cooling_active)
            data.heating_active = self._heating_active(options, outdoor_temp, previous.heating_active)

        await self._apply_control_states(options, data)
        if data.heating_active and data.heating_target_setpoint is not None:
            data.target_setpoint = data.heating_target_setpoint
        elif data.cooling_target_setpoint is not None:
            data.target_setpoint = data.cooling_target_setpoint
        return data

    def _subscribe_state_changes(self) -> None:
        """Refresh when configured source or controlled entities change."""

        entities = {
            entity_id
            for entity_id in (
                self.merged_options.get(CONF_OUTDOOR_TEMP_SENSOR),
                self.merged_options.get(CONF_HUMIDITY_SENSOR),
                self.merged_options.get(CONF_COOLING_CLIMATE),
                self.merged_options.get(CONF_HEATING_CLIMATE),
            )
            if entity_id
        }
        if not entities:
            return

        @callback
        def _state_changed(_: Any) -> None:
            self.async_set_updated_data(self.data or HvacCurveData())
            self.config_entry.async_create_background_task(
                self.hass,
                self.async_request_refresh(),
                "hvac_setpoint_curve_refresh",
            )

        self._unsub_state_change = async_track_state_change_event(
            self.hass,
            list(entities),
            _state_changed,
        )

    def refresh_listeners(self) -> None:
        """Refresh entity subscriptions after options change."""

        if self._unsub_state_change is not None:
            self._unsub_state_change()
            self._unsub_state_change = None
        self._subscribe_state_changes()

    def _get_outdoor_temperature(self, options: dict[str, Any]) -> float | None:
        """Resolve outdoor temperature from explicit sensor, climate attributes, or weather entity."""

        explicit_sensor = options.get(CONF_OUTDOOR_TEMP_SENSOR)
        if explicit_sensor:
            return self._get_float_state(explicit_sensor)

        for state in self.hass.states.async_all("weather"):
            temp = _float_or_none(state.attributes.get(ATTR_TEMPERATURE))
            if temp is not None:
                return temp

        return None

    def _get_float_state(self, entity_id: str | None) -> float | None:
        """Read an entity state as float."""

        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        return _state_as_float(state)

    def _cooling_active(
        self,
        options: dict[str, Any],
        outdoor_temp: float,
        previous_active: bool,
    ) -> bool:
        """Return the cooling state after applying hysteresis."""

        decision = decide_cooling(
            outdoor_temp,
            previous_active,
            float(options.get(CONF_COOLING_ON_THRESHOLD, DEFAULT_COOLING_ON_THRESHOLD)),
            float(options.get(CONF_COOLING_OFF_THRESHOLD, DEFAULT_COOLING_OFF_THRESHOLD)),
        )
        return decision.active

    def _heating_active(
        self,
        options: dict[str, Any],
        outdoor_temp: float,
        previous_active: bool,
    ) -> bool:
        """Return the heating state after applying hysteresis."""

        decision = decide_heating(
            outdoor_temp,
            previous_active,
            float(options.get(CONF_HEATING_ON_THRESHOLD, DEFAULT_HEATING_ON_THRESHOLD)),
            float(options.get(CONF_HEATING_OFF_THRESHOLD, DEFAULT_HEATING_OFF_THRESHOLD)),
        )
        return decision.active

    async def _apply_control_states(self, options: dict[str, Any], data: HvacCurveData) -> None:
        """Apply heating and cooling without issuing conflicting commands."""

        cooling_entity = options.get(CONF_COOLING_CLIMATE)
        heating_entity = options.get(CONF_HEATING_CLIMATE)

        if cooling_entity and cooling_entity == heating_entity:
            if data.cooling_active and data.heating_active:
                _LOGGER.error("Heating and cooling are both active for %s; turning it off", cooling_entity)
                await self._apply_climate_control(cooling_entity, HVACMode.OFF, False, None)
            elif data.heating_active:
                await self._apply_climate_control(
                    heating_entity,
                    HVACMode.HEAT,
                    True,
                    data.heating_target_setpoint,
                )
            elif data.cooling_active:
                await self._apply_climate_control(
                    cooling_entity,
                    HVACMode.COOL,
                    True,
                    data.cooling_target_setpoint,
                )
            else:
                await self._apply_climate_control(cooling_entity, HVACMode.OFF, False, None)
            return

        if cooling_entity:
            await self._apply_climate_control(
                cooling_entity,
                HVACMode.COOL,
                data.cooling_active,
                data.cooling_target_setpoint,
            )
        if heating_entity:
            await self._apply_climate_control(
                heating_entity,
                HVACMode.HEAT,
                data.heating_active,
                data.heating_target_setpoint,
            )

    async def _apply_climate_control(
        self,
        entity_id: str,
        hvac_mode: HVACMode,
        active: bool,
        target_setpoint: float | None,
    ) -> None:
        """Call climate services for a linked entity."""

        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            _LOGGER.warning("Skipping %s because it is unavailable", entity_id)
            return

        if active and target_setpoint is not None:
            try:
                supported_target = _supported_target_temperature(state, target_setpoint)
                if state.state != hvac_mode:
                    await self.hass.services.async_call(
                        "climate",
                        SERVICE_SET_HVAC_MODE,
                        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: hvac_mode},
                        blocking=True,
                    )
                current_target = _float_or_none(state.attributes.get(ATTR_TEMPERATURE))
                if current_target is None or abs(current_target - supported_target) >= 0.05:
                    await self.hass.services.async_call(
                        "climate",
                        SERVICE_SET_TEMPERATURE,
                        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: supported_target},
                        blocking=True,
                    )
            except HomeAssistantError as err:
                _LOGGER.error("Failed to control %s: %s", entity_id, err)
            return

        if state.state != HVACMode.OFF:
            try:
                await self.hass.services.async_call(
                    "climate",
                    SERVICE_SET_HVAC_MODE,
                    {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
                    blocking=True,
                )
            except HomeAssistantError as err:
                _LOGGER.error("Failed to turn off %s: %s", entity_id, err)


def _state_as_float(state: State) -> float | None:
    """Parse numeric state safely."""

    if state.state in {"unknown", "unavailable"}:
        return None
    return _float_or_none(state.state)


def _float_or_none(value: Any) -> float | None:
    """Parse a float safely."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _supported_target_temperature(state: State, target_setpoint: float) -> float:
    """Fit a target to the linked climate entity's range and temperature step."""

    minimum = _float_or_none(state.attributes.get(ATTR_MIN_TEMP))
    maximum = _float_or_none(state.attributes.get(ATTR_MAX_TEMP))
    step = _positive_decimal_or_none(state.attributes.get(ATTR_TARGET_TEMP_STEP))

    target = Decimal(str(target_setpoint))
    if minimum is not None:
        target = max(target, Decimal(str(minimum)))
    if maximum is not None:
        target = min(target, Decimal(str(maximum)))

    if step is not None:
        # Climate temperature steps are increments on the temperature scale.
        target = (target / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step
        if minimum is not None:
            target = max(target, Decimal(str(minimum)))
        if maximum is not None:
            target = min(target, Decimal(str(maximum)))

    return float(target)


def _positive_decimal_or_none(value: Any) -> Decimal | None:
    """Parse a positive decimal value safely."""

    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def _curve_for_mode(options: dict[str, Any], key: str, default: list[dict[str, float]]) -> list[dict[str, float]]:
    """Return a mode-specific curve, migrating legacy shared curves as a fallback."""

    return options.get(key) or options.get(CONF_CURVE_POINTS) or default
