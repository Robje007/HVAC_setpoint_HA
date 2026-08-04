"""Coordinator and control logic for HVAC Setpoint Curve."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from homeassistant.components.climate import ATTR_HVAC_MODE, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONTROLLER_ENABLED,
    CONF_COOLING_CLIMATE,
    CONF_COOLING_CURVE_POINTS,
    CONF_COOLING_OFF_THRESHOLD,
    CONF_COOLING_ON_THRESHOLD,
    CONF_COOLING_PRESET,
    CONF_CURVE_POINTS,
    CONF_HEATING_CLIMATE,
    CONF_HEATING_CURVE_POINTS,
    CONF_HEATING_OFF_THRESHOLD,
    CONF_HEATING_ON_THRESHOLD,
    CONF_HEATING_PRESET,
    CONF_HUMIDITY_SENSOR,
    CONF_INDOOR_SETTLING_HOURS,
    CONF_INDOOR_START_DELTA,
    CONF_INDOOR_STOP_DELTA,
    CONF_INDOOR_TEMP_SENSOR,
    CONF_OPPOSITE_ENTITY_INTERLOCK,
    CONF_OUTDOOR_AVERAGING_HOURS,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_PRESET,
    CONF_SENSOR_ONLY,
    DEFAULT_CONTROLLER_ENABLED,
    DEFAULT_COOLING_CURVE_POINTS,
    DEFAULT_COOLING_OFF_THRESHOLD,
    DEFAULT_COOLING_ON_THRESHOLD,
    DEFAULT_HEATING_CURVE_POINTS,
    DEFAULT_HEATING_OFF_THRESHOLD,
    DEFAULT_HEATING_ON_THRESHOLD,
    DEFAULT_INDOOR_SETTLING_HOURS,
    DEFAULT_INDOOR_START_DELTA,
    DEFAULT_INDOOR_STOP_DELTA,
    DEFAULT_OPPOSITE_ENTITY_INTERLOCK,
    DEFAULT_OUTDOOR_AVERAGING_HOURS,
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
ATTR_CURRENT_TEMPERATURE = "current_temperature"


@dataclass(slots=True)
class HvacCurveData:
    """Computed integration state."""

    target_setpoint: float | None = None
    cooling_target_setpoint: float | None = None
    heating_target_setpoint: float | None = None
    outdoor_temperature_used: float | None = None
    outdoor_temperature_average: float | None = None
    humidity_used: float | None = None
    cooling_indoor_temperature_used: float | None = None
    heating_indoor_temperature_used: float | None = None
    cooling_indoor_temperature_source: str | None = None
    heating_indoor_temperature_source: str | None = None
    cooling_stabilizing: bool = False
    heating_stabilizing: bool = False
    active_preset: str | None = None
    cooling_preset: str | None = None
    heating_preset: str | None = None
    cooling_active: bool = False
    heating_active: bool = False


class HvacSetpointCoordinator(DataUpdateCoordinator[HvacCurveData]):
    """Coordinate setpoint calculation and optional climate control."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""

        self._unsub_state_change: Any = None
        self._outdoor_samples: deque[tuple[datetime, float]] = deque()
        self._cooling_satisfied_since: datetime | None = None
        self._heating_satisfied_since: datetime | None = None
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
        await super().async_shutdown()

    @property
    def merged_options(self) -> dict[str, Any]:
        """Return entry data and live options merged together."""

        return {**self.config_entry.data, **self.config_entry.options}

    async def _async_update_data(self) -> HvacCurveData:
        """Recompute data and run optional control actions."""

        options = self.merged_options
        previous = self.data or HvacCurveData()
        previous_cooling_active = self._previous_mode_active(
            options,
            CONF_COOLING_CLIMATE,
            HVACMode.COOL,
            previous.cooling_active,
        )
        previous_heating_active = self._previous_mode_active(
            options,
            CONF_HEATING_CLIMATE,
            HVACMode.HEAT,
            previous.heating_active,
        )
        outdoor_temp = self._get_outdoor_temperature(options)
        humidity = self._get_float_state(options.get(CONF_HUMIDITY_SENSOR))
        controller_enabled = bool(options.get(CONF_CONTROLLER_ENABLED, DEFAULT_CONTROLLER_ENABLED))

        if outdoor_temp is None:
            _LOGGER.warning("No usable outdoor temperature found for %s", self.config_entry.title)
            data = HvacCurveData(
                active_preset=options.get(CONF_PRESET),
                cooling_preset=options.get(CONF_COOLING_PRESET, options.get(CONF_PRESET)),
                heating_preset=options.get(CONF_HEATING_PRESET, options.get(CONF_PRESET)),
                cooling_active=previous_cooling_active if controller_enabled else False,
                heating_active=previous_heating_active if controller_enabled else False,
            )
            if controller_enabled:
                _LOGGER.warning(
                    "Leaving linked HVAC unchanged for %s until outdoor temperature is available again",
                    self.config_entry.title,
                )
            return data

        cooling_target_setpoint = computed_setpoint(
            _curve_for_mode(options, CONF_COOLING_CURVE_POINTS, DEFAULT_COOLING_CURVE_POINTS),
            outdoor_temp,
            humidity,
            humidity_direction=-1,
        )
        heating_target_setpoint = computed_setpoint(
            _curve_for_mode(options, CONF_HEATING_CURVE_POINTS, DEFAULT_HEATING_CURVE_POINTS),
            outdoor_temp,
            humidity,
        )
        now = dt_util.utcnow()
        outdoor_average = _time_weighted_average(
            self._outdoor_samples,
            outdoor_temp,
            float(options.get(CONF_OUTDOOR_AVERAGING_HOURS, DEFAULT_OUTDOOR_AVERAGING_HOURS)),
            now,
        )
        cooling_indoor, cooling_indoor_source = self._get_indoor_temperature(options, CONF_COOLING_CLIMATE)
        heating_indoor, heating_indoor_source = self._get_indoor_temperature(options, CONF_HEATING_CLIMATE)
        data = HvacCurveData(
            target_setpoint=cooling_target_setpoint,
            cooling_target_setpoint=cooling_target_setpoint,
            heating_target_setpoint=heating_target_setpoint,
            outdoor_temperature_used=outdoor_temp,
            outdoor_temperature_average=outdoor_average,
            humidity_used=humidity,
            cooling_indoor_temperature_used=cooling_indoor,
            heating_indoor_temperature_used=heating_indoor,
            cooling_indoor_temperature_source=cooling_indoor_source,
            heating_indoor_temperature_source=heating_indoor_source,
            active_preset=options.get(CONF_PRESET),
            cooling_preset=options.get(CONF_COOLING_PRESET, options.get(CONF_PRESET)),
            heating_preset=options.get(CONF_HEATING_PRESET, options.get(CONF_PRESET)),
            cooling_active=previous_cooling_active,
            heating_active=previous_heating_active,
        )

        validation_error = threshold_error(
            options,
            cooling_enabled=bool(options.get(CONF_COOLING_CLIMATE) or options.get(CONF_SENSOR_ONLY)),
            heating_enabled=bool(options.get(CONF_HEATING_CLIMATE) or options.get(CONF_SENSOR_ONLY)),
        )
        if not controller_enabled:
            data.cooling_active = False
            data.heating_active = False
        elif validation_error:
            _LOGGER.error("Not controlling HVAC for %s: %s", self.config_entry.title, validation_error)
            data.cooling_active = False
            data.heating_active = False
        else:
            data.cooling_active = self._cooling_active(
                options,
                outdoor_average,
                previous_cooling_active,
                cooling_indoor,
                cooling_target_setpoint,
                now,
            )
            data.heating_active = self._heating_active(
                options,
                outdoor_average,
                previous_heating_active,
                heating_indoor,
                heating_target_setpoint,
                now,
            )
            self._resolve_shared_entity_conflict(options, data)
            data.cooling_stabilizing = data.cooling_active and self._cooling_satisfied_since is not None
            data.heating_stabilizing = data.heating_active and self._heating_satisfied_since is not None

        if controller_enabled:
            await self._apply_control_states(options, data)
        cooling_enabled = bool(options.get(CONF_COOLING_CLIMATE) or options.get(CONF_SENSOR_ONLY))
        heating_enabled = bool(options.get(CONF_HEATING_CLIMATE) or options.get(CONF_SENSOR_ONLY))
        if data.heating_active and data.heating_target_setpoint is not None:
            data.target_setpoint = data.heating_target_setpoint
        elif data.cooling_active and data.cooling_target_setpoint is not None:
            data.target_setpoint = data.cooling_target_setpoint
        elif heating_enabled and not cooling_enabled:
            data.target_setpoint = data.heating_target_setpoint
        else:
            data.target_setpoint = data.cooling_target_setpoint
        return data

    def _resolve_shared_entity_conflict(self, options: dict[str, Any], data: HvacCurveData) -> None:
        """Keep shared or interlocked equipment in exactly one operating mode."""

        entity_id = options.get(CONF_COOLING_CLIMATE)
        heating_entity = options.get(CONF_HEATING_CLIMATE)
        interlocked = bool(options.get(CONF_OPPOSITE_ENTITY_INTERLOCK, DEFAULT_OPPOSITE_ENTITY_INTERLOCK))
        if not entity_id or not heating_entity or (entity_id != heating_entity and not interlocked):
            return
        if not data.cooling_active or not data.heating_active:
            return

        cooling_state = self.hass.states.get(entity_id)
        heating_state = self.hass.states.get(heating_entity)
        if entity_id == heating_entity:
            if cooling_state is not None and cooling_state.state == HVACMode.HEAT:
                data.cooling_active = False
                self._cooling_satisfied_since = None
                return
            if cooling_state is not None and cooling_state.state == HVACMode.COOL:
                data.heating_active = False
                self._heating_satisfied_since = None
                return
        else:
            cooling_running = cooling_state is not None and cooling_state.state == HVACMode.COOL
            heating_running = heating_state is not None and heating_state.state == HVACMode.HEAT
            if cooling_running != heating_running:
                data.heating_active = not cooling_running
                data.cooling_active = cooling_running
                if cooling_running:
                    self._heating_satisfied_since = None
                else:
                    self._cooling_satisfied_since = None
                return

        cooling_demand = (
            data.cooling_indoor_temperature_used - data.cooling_target_setpoint
            if data.cooling_indoor_temperature_used is not None and data.cooling_target_setpoint is not None
            else float("-inf")
        )
        heating_demand = (
            data.heating_target_setpoint - data.heating_indoor_temperature_used
            if data.heating_indoor_temperature_used is not None and data.heating_target_setpoint is not None
            else float("-inf")
        )
        if heating_demand > cooling_demand:
            data.cooling_active = False
            self._cooling_satisfied_since = None
        else:
            data.heating_active = False
            self._heating_satisfied_since = None

    def _subscribe_state_changes(self) -> None:
        """Refresh when configured source or controlled entities change."""

        entities = {
            entity_id
            for entity_id in (
                self.merged_options.get(CONF_OUTDOOR_TEMP_SENSOR),
                self.merged_options.get(CONF_INDOOR_TEMP_SENSOR),
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

    def _get_indoor_temperature(
        self,
        options: dict[str, Any],
        climate_key: str,
    ) -> tuple[float | None, str | None]:
        """Read an explicit indoor sensor or the linked climate's current temperature."""

        indoor_sensor = options.get(CONF_INDOOR_TEMP_SENSOR)
        indoor_temperature = self._get_float_state(indoor_sensor)
        if indoor_temperature is not None:
            return indoor_temperature, indoor_sensor

        climate_entity = options.get(climate_key)
        state = self.hass.states.get(climate_entity) if climate_entity else None
        if state is None or state.state in {"unknown", "unavailable"}:
            return None, None
        indoor_temperature = _float_or_none(state.attributes.get(ATTR_CURRENT_TEMPERATURE))
        return indoor_temperature, climate_entity if indoor_temperature is not None else None

    def _previous_mode_active(
        self,
        options: dict[str, Any],
        climate_key: str,
        hvac_mode: HVACMode,
        previous_active: bool,
    ) -> bool:
        """Restore an active cycle from the climate mode on the first refresh."""

        if self.data is not None:
            return previous_active
        climate_entity = options.get(climate_key)
        state = self.hass.states.get(climate_entity) if climate_entity else None
        return state is not None and state.state == hvac_mode

    def _cooling_active(
        self,
        options: dict[str, Any],
        outdoor_temp: float,
        previous_active: bool,
        indoor_temp: float | None,
        target_setpoint: float,
        now: datetime,
    ) -> bool:
        """Return the cooling state after applying hysteresis."""

        if indoor_temp is not None:
            start_delta = float(options.get(CONF_INDOOR_START_DELTA, DEFAULT_INDOOR_START_DELTA))
            stop_delta = float(options.get(CONF_INDOOR_STOP_DELTA, DEFAULT_INDOOR_STOP_DELTA))
            if previous_active:
                outdoor_allows_release = outdoor_temp < float(
                    options.get(CONF_COOLING_OFF_THRESHOLD, DEFAULT_COOLING_OFF_THRESHOLD)
                )
                indoor_satisfied = indoor_temp <= target_setpoint + stop_delta
                if not outdoor_allows_release or not indoor_satisfied:
                    self._cooling_satisfied_since = None
                    return True
                if self._cooling_satisfied_since is None:
                    self._cooling_satisfied_since = now
                settling_hours = float(options.get(CONF_INDOOR_SETTLING_HOURS, DEFAULT_INDOOR_SETTLING_HOURS))
                if now - self._cooling_satisfied_since < timedelta(hours=settling_hours):
                    return True
                self._cooling_satisfied_since = None
                return False
            self._cooling_satisfied_since = None
            if indoor_temp < target_setpoint + start_delta:
                return False
        else:
            self._cooling_satisfied_since = None

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
        indoor_temp: float | None,
        target_setpoint: float,
        now: datetime,
    ) -> bool:
        """Return the heating state after applying hysteresis."""

        if indoor_temp is not None:
            start_delta = float(options.get(CONF_INDOOR_START_DELTA, DEFAULT_INDOOR_START_DELTA))
            stop_delta = float(options.get(CONF_INDOOR_STOP_DELTA, DEFAULT_INDOOR_STOP_DELTA))
            if previous_active:
                outdoor_allows_release = outdoor_temp > float(
                    options.get(CONF_HEATING_OFF_THRESHOLD, DEFAULT_HEATING_OFF_THRESHOLD)
                )
                indoor_satisfied = indoor_temp >= target_setpoint - stop_delta
                if not outdoor_allows_release or not indoor_satisfied:
                    self._heating_satisfied_since = None
                    return True
                if self._heating_satisfied_since is None:
                    self._heating_satisfied_since = now
                settling_hours = float(options.get(CONF_INDOOR_SETTLING_HOURS, DEFAULT_INDOOR_SETTLING_HOURS))
                if now - self._heating_satisfied_since < timedelta(hours=settling_hours):
                    return True
                self._heating_satisfied_since = None
                return False
            self._heating_satisfied_since = None
            if indoor_temp > target_setpoint - start_delta:
                return False
        else:
            self._heating_satisfied_since = None

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
        interlocked = bool(options.get(CONF_OPPOSITE_ENTITY_INTERLOCK, DEFAULT_OPPOSITE_ENTITY_INTERLOCK))

        if cooling_entity and cooling_entity == heating_entity:
            if data.cooling_active and data.heating_active:
                _LOGGER.error("Heating and cooling are both active for %s; leaving it unchanged", cooling_entity)
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
                state = self.hass.states.get(cooling_entity)
                current_mode = (
                    HVACMode(state.state)
                    if state and state.state in {HVACMode.COOL, HVACMode.HEAT}
                    else HVACMode.COOL
                )
                await self._apply_climate_control(
                    cooling_entity,
                    current_mode,
                    False,
                    (
                        data.heating_target_setpoint
                        if current_mode == HVACMode.HEAT
                        else data.cooling_target_setpoint
                    ),
                )
            return

        if interlocked and cooling_entity and heating_entity:
            if data.heating_active:
                if not await self._async_turn_off_opposite(cooling_entity):
                    return
            elif data.cooling_active:
                if not await self._async_turn_off_opposite(heating_entity):
                    return

        if cooling_entity and not (interlocked and data.heating_active):
            await self._apply_climate_control(
                cooling_entity,
                HVACMode.COOL,
                data.cooling_active,
                data.cooling_target_setpoint,
            )
        if heating_entity and not (interlocked and data.cooling_active):
            await self._apply_climate_control(
                heating_entity,
                HVACMode.HEAT,
                data.heating_active,
                data.heating_target_setpoint,
            )

    async def _async_turn_off_opposite(self, entity_id: str) -> bool:
        """Turn off an idle, separately linked entity before starting its opposite."""

        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            _LOGGER.warning("Cannot verify opposite HVAC entity %s; skipping mode change", entity_id)
            return False
        if state.state == HVACMode.OFF:
            return True
        try:
            await self.hass.services.async_call(
                "climate",
                SERVICE_SET_HVAC_MODE,
                {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.error("Failed to switch off opposite HVAC entity %s: %s", entity_id, err)
            return False
        return True

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

        # An inactive curve session must never power equipment off. If the
        # linked entity is already in this mode, keep its thermostat supplied
        # with the current curve target and let the equipment cycle itself.
        should_set_target = target_setpoint is not None and (active or state.state == hvac_mode)
        if should_set_target and target_setpoint is not None:
            try:
                supported_target = _supported_target_temperature(state, target_setpoint)
                if active and state.state != hvac_mode:
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


def _time_weighted_average(
    samples: deque[tuple[datetime, float]],
    current_value: float,
    window_hours: float,
    now: datetime,
) -> float:
    """Update samples and return a time-weighted average over the configured window."""

    window = timedelta(hours=max(0.0, window_hours))
    if window <= timedelta(0):
        samples.clear()
        samples.append((now, current_value))
        return current_value

    if samples and now < samples[-1][0]:
        samples.clear()
    if not samples or samples[-1][1] != current_value:
        samples.append((now, current_value))

    cutoff = now - window
    while len(samples) > 1 and samples[1][0] <= cutoff:
        samples.popleft()

    points = list(samples)
    average_start = max(cutoff, points[0][0])
    duration = (now - average_start).total_seconds()
    if duration <= 0:
        return current_value

    weighted_total = 0.0
    for index, (started_at, value) in enumerate(points):
        segment_start = max(started_at, average_start)
        segment_end = points[index + 1][0] if index + 1 < len(points) else now
        if segment_end > segment_start:
            weighted_total += value * (segment_end - segment_start).total_seconds()
    return weighted_total / duration


def _curve_for_mode(options: dict[str, Any], key: str, default: list[dict[str, float]]) -> list[dict[str, float]]:
    """Return a mode-specific curve, migrating legacy shared curves as a fallback."""

    return options.get(key) or options.get(CONF_CURVE_POINTS) or default
