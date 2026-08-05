"""Config flow for HVAC Setpoint Curve."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_COOLING_CLIMATE,
    CONF_COOLING_CURVE_POINTS,
    CONF_COOLING_OFF_THRESHOLD,
    CONF_COOLING_ON_THRESHOLD,
    CONF_COOLING_PRESET,
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
    DEFAULT_COOLING_CURVE_POINTS,
    DEFAULT_COOLING_ON_THRESHOLD,
    DEFAULT_HEATING_CURVE_POINTS,
    DEFAULT_HEATING_ON_THRESHOLD,
    DEFAULT_INDOOR_SETTLING_HOURS,
    DEFAULT_INDOOR_START_DELTA,
    DEFAULT_INDOOR_STOP_DELTA,
    DEFAULT_OPPOSITE_ENTITY_INTERLOCK,
    DEFAULT_OUTDOOR_AVERAGING_HOURS,
    DEFAULT_PRESET,
    DOMAIN,
    MAX_CURVE_POINTS,
    MIN_CURVE_POINTS,
    PRESET_CUSTOM,
    PRESET_EMPTY,
    PRESETS,
    SETPOINT_MAX,
    SETPOINT_MIN,
    TEMPERATURE_MAX,
    TEMPERATURE_MIN,
    preset_changeovers,
    preset_curve,
    preset_name,
)
from .curve import CurvePoint, parse_curve_points, serialize_curve_points

_LINKED_ENTITY_KEYS = (
    CONF_COOLING_CLIMATE,
    CONF_HEATING_CLIMATE,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_INDOOR_TEMP_SENSOR,
    CONF_HUMIDITY_SENSOR,
)


def _entity_selector(domain: str) -> selector.EntitySelector:
    """Create an entity selector for a domain."""

    return selector.EntitySelector(selector.EntitySelectorConfig(domain=domain))


def _climate_selector(hass: Any, hvac_mode: str) -> selector.EntitySelector:
    """Create a climate selector excluding entities known not to support a mode."""

    incompatible_entities = [
        state.entity_id
        for state in hass.states.async_all("climate")
        if (modes := state.attributes.get("hvac_modes")) is not None and hvac_mode not in modes
    ]
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="climate",
            exclude_entities=incompatible_entities,
        )
    )


def _preset_options(language: str, include_empty: bool | None = True) -> list[dict[str, str]]:
    """Return select options for presets."""

    options = [
        {"value": key, "label": preset_name(key, language)}
        for key in ("comfort", "eco")
    ]
    options.append({"value": PRESET_CUSTOM, "label": preset_name(PRESET_CUSTOM, language)})
    return options


def _mode_preset_schema(hass: Any, options: dict[str, Any], *, include_empty: bool | None) -> vol.Schema:
    """Build one understandable building-profile field."""

    current = options.get(CONF_PRESET, DEFAULT_PRESET)
    if current not in {"comfort", "eco", PRESET_CUSTOM}:
        current = PRESET_CUSTOM
    return vol.Schema(
        {
            vol.Required(CONF_PRESET, default=current): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_preset_options(hass.config.language, include_empty=include_empty),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def _apply_mode_presets(target: dict[str, Any], selected: dict[str, Any]) -> bool:
    """Apply one profile to heating, cooling and changeover behavior."""

    preset = selected[CONF_PRESET]
    preset = PRESET_CUSTOM if preset == PRESET_EMPTY else preset
    target[CONF_PRESET] = preset
    target[CONF_COOLING_PRESET] = preset
    target[CONF_HEATING_PRESET] = preset
    if preset not in PRESETS:
        return True
    target[CONF_COOLING_CURVE_POINTS] = preset_curve(preset, "cooling")
    target[CONF_HEATING_CURVE_POINTS] = preset_curve(preset, "heating")
    heating_changeover, cooling_changeover = preset_changeovers(preset)
    target[CONF_HEATING_ON_THRESHOLD] = heating_changeover
    target[CONF_HEATING_OFF_THRESHOLD] = heating_changeover + 1.5
    target[CONF_COOLING_ON_THRESHOLD] = cooling_changeover
    target[CONF_COOLING_OFF_THRESHOLD] = cooling_changeover - 1.5
    return False


def _optional_entity_field(key: str, label_options: dict[str, Any]) -> vol.Optional:
    """Create an optional field that remains clearable when pre-filled."""

    if label_options.get(key):
        return vol.Optional(key, description={"suggested_value": label_options[key]})
    return vol.Optional(key)


def _control_behavior_schema(options: dict[str, Any]) -> vol.Schema:
    """Build thermal-inertia and indoor-demand settings."""

    return vol.Schema(
        {
            vol.Required(
                CONF_OUTDOOR_AVERAGING_HOURS,
                default=options.get(CONF_OUTDOOR_AVERAGING_HOURS, DEFAULT_OUTDOOR_AVERAGING_HOURS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=24,
                    step=0.5,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="h",
                )
            ),
            vol.Required(
                CONF_INDOOR_START_DELTA,
                default=options.get(CONF_INDOOR_START_DELTA, DEFAULT_INDOOR_START_DELTA),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=3,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="°C",
                )
            ),
            vol.Required(
                CONF_INDOOR_STOP_DELTA,
                default=options.get(CONF_INDOOR_STOP_DELTA, DEFAULT_INDOOR_STOP_DELTA),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=3,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="°C",
                )
            ),
            vol.Required(
                CONF_INDOOR_SETTLING_HOURS,
                default=options.get(CONF_INDOOR_SETTLING_HOURS, DEFAULT_INDOOR_SETTLING_HOURS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=12,
                    step=0.5,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="h",
                )
            ),
            vol.Required(
                CONF_OPPOSITE_ENTITY_INTERLOCK,
                default=options.get(CONF_OPPOSITE_ENTITY_INTERLOCK, DEFAULT_OPPOSITE_ENTITY_INTERLOCK),
            ): selector.BooleanSelector(),
        }
    )


def _climate_mode_errors(hass: Any, options: dict[str, Any]) -> dict[str, str]:
    """Return field errors for linked climate entities lacking a requested mode."""

    errors: dict[str, str] = {}
    for key, mode, error in (
        (CONF_COOLING_CLIMATE, "cool", "unsupported_cooling_mode"),
        (CONF_HEATING_CLIMATE, "heat", "unsupported_heating_mode"),
    ):
        entity_id = options.get(key)
        state = hass.states.get(entity_id) if entity_id else None
        supported_modes = state.attributes.get("hvac_modes") if state else None
        if supported_modes is not None and mode not in supported_modes:
            errors[key] = error
    return errors


def _linked_entities_schema(hass: Any, options: dict[str, Any], *, include_name: bool = False) -> vol.Schema:
    """Build linked entities form schema."""

    fields: dict[vol.Marker, Any] = {}
    if include_name:
        fields[vol.Required(CONF_NAME, default=options.get(CONF_NAME, "Living room AC curve"))] = str

    fields.update(
        {
            _optional_entity_field(CONF_COOLING_CLIMATE, options): _climate_selector(hass, "cool"),
            _optional_entity_field(CONF_HEATING_CLIMATE, options): _climate_selector(hass, "heat"),
            _optional_entity_field(CONF_OUTDOOR_TEMP_SENSOR, options): _entity_selector("sensor"),
            _optional_entity_field(CONF_INDOOR_TEMP_SENSOR, options): _entity_selector("sensor"),
            _optional_entity_field(CONF_HUMIDITY_SENSOR, options): _entity_selector("sensor"),
            vol.Required(CONF_SENSOR_ONLY, default=options.get(CONF_SENSOR_ONLY, False)): selector.BooleanSelector(),
        }
    )
    return vol.Schema(fields)


def _curve_schema(
    heating_points: list[CurvePoint] | None = None,
    cooling_points: list[CurvePoint] | None = None,
    options: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build one combined heating, neutral-zone and cooling editor."""

    heating_points = heating_points or parse_curve_points(DEFAULT_HEATING_CURVE_POINTS)
    cooling_points = cooling_points or parse_curve_points(DEFAULT_COOLING_CURVE_POINTS)
    options = options or {}
    point_count = min(len(heating_points), len(cooling_points))
    fields: dict[vol.Marker, Any] = {
        vol.Required("point_count", default=point_count): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=MIN_CURVE_POINTS,
                max=MAX_CURVE_POINTS,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
            )
        )
    }

    for index in range(MAX_CURVE_POINTS):
        heating_point = heating_points[index] if index < len(heating_points) else None
        cooling_point = cooling_points[index] if index < len(cooling_points) else None
        point = heating_point or cooling_point
        outdoor_key = f"outdoor_temp_{index + 1}"
        outdoor_marker = vol.Optional(outdoor_key, default=point.outdoor_temp) if point else vol.Optional(outdoor_key)
        fields[outdoor_marker] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=TEMPERATURE_MIN,
                max=TEMPERATURE_MAX,
                step=0.1,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="°C",
            )
        )
        for prefix, curve_point in (("heating", heating_point), ("cooling", cooling_point)):
            key = f"{prefix}_setpoint_{index + 1}"
            marker = vol.Optional(key, default=curve_point.setpoint) if curve_point else vol.Optional(key)
            fields[marker] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=SETPOINT_MIN,
                    max=SETPOINT_MAX,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="°C",
                )
            )
    fields[
        vol.Required(
            CONF_HEATING_ON_THRESHOLD,
            default=options.get(CONF_HEATING_ON_THRESHOLD, DEFAULT_HEATING_ON_THRESHOLD),
        )
    ] = selector.NumberSelector(
        selector.NumberSelectorConfig(min=5, max=30, step=0.5, unit_of_measurement="°C")
    )
    fields[
        vol.Required(
            CONF_COOLING_ON_THRESHOLD,
            default=options.get(CONF_COOLING_ON_THRESHOLD, DEFAULT_COOLING_ON_THRESHOLD),
        )
    ] = selector.NumberSelector(
        selector.NumberSelectorConfig(min=5, max=35, step=0.5, unit_of_measurement="°C")
    )
    return vol.Schema(fields)


def _points_from_slots(user_input: dict[str, Any]) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    """Convert the combined editor into separate internal curves."""

    point_count = int(user_input["point_count"])
    heating_points = []
    cooling_points = []
    for index in range(point_count):
        outdoor = user_input.get(f"outdoor_temp_{index + 1}")
        heating = user_input.get(f"heating_setpoint_{index + 1}")
        cooling = user_input.get(f"cooling_setpoint_{index + 1}")
        if outdoor is None or heating is None or cooling is None or float(heating) >= float(cooling):
            raise ValueError("missing_point")
        heating_points.append(CurvePoint(float(outdoor), float(heating)))
        cooling_points.append(CurvePoint(float(outdoor), float(cooling)))
    return (
        serialize_curve_points(parse_curve_points(heating_points)),
        serialize_curve_points(parse_curve_points(cooling_points)),
    )


def _options_from_entry(entry: config_entries.ConfigEntry) -> dict[str, Any]:
    """Merge entry data and options."""

    return {**entry.data, **entry.options}


class HvacSetpointConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 5

    def __init__(self) -> None:
        """Initialize flow state."""

        self._setup_data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> HvacSetpointOptionsFlow:
        """Return the options flow."""

        return HvacSetpointOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle initial setup."""

        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_SENSOR_ONLY) and not (
                user_input.get(CONF_COOLING_CLIMATE) or user_input.get(CONF_HEATING_CLIMATE)
            ):
                errors["base"] = "missing_control_or_sensor_only"
            else:
                errors.update(_climate_mode_errors(self.hass, user_input))
                if not errors:
                    self._setup_data = dict(user_input)
                    return await self.async_step_preset()

        return self.async_show_form(
            step_id="user",
            data_schema=_linked_entities_schema(self.hass, self._setup_data, include_name=True),
            errors=errors,
        )

    async def async_step_preset(self, user_input: dict[str, Any] | None = None):
        """Choose one building profile."""

        if user_input is not None:
            needs_custom = _apply_mode_presets(self._setup_data, user_input)
            self._setup_data.setdefault(CONF_COOLING_CURVE_POINTS, DEFAULT_COOLING_CURVE_POINTS)
            self._setup_data.setdefault(CONF_HEATING_CURVE_POINTS, DEFAULT_HEATING_CURVE_POINTS)
            if needs_custom:
                return await self.async_step_custom_curve()
            return await self._async_finish_setup()

        return self.async_show_form(
            step_id="preset",
            data_schema=_mode_preset_schema(self.hass, self._setup_data, include_empty=None),
        )

    async def async_step_custom_curve(self, user_input: dict[str, Any] | None = None):
        """Create one combined custom building profile."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                heating_points, cooling_points = _points_from_slots(user_input)
                if float(user_input[CONF_HEATING_ON_THRESHOLD]) >= float(user_input[CONF_COOLING_ON_THRESHOLD]):
                    raise ValueError("overlapping_changeover")
            except ValueError:
                errors["base"] = "invalid_curve"
            else:
                self._setup_data[CONF_PRESET] = PRESET_CUSTOM
                self._setup_data[CONF_COOLING_PRESET] = PRESET_CUSTOM
                self._setup_data[CONF_HEATING_PRESET] = PRESET_CUSTOM
                self._setup_data[CONF_COOLING_CURVE_POINTS] = cooling_points
                self._setup_data[CONF_HEATING_CURVE_POINTS] = heating_points
                heating_changeover = float(user_input[CONF_HEATING_ON_THRESHOLD])
                cooling_changeover = float(user_input[CONF_COOLING_ON_THRESHOLD])
                self._setup_data[CONF_HEATING_ON_THRESHOLD] = heating_changeover
                self._setup_data[CONF_HEATING_OFF_THRESHOLD] = heating_changeover + 1.5
                self._setup_data[CONF_COOLING_ON_THRESHOLD] = cooling_changeover
                self._setup_data[CONF_COOLING_OFF_THRESHOLD] = cooling_changeover - 1.5
                return await self._async_finish_setup()

        heating = parse_curve_points(self._setup_data.get(CONF_HEATING_CURVE_POINTS, DEFAULT_HEATING_CURVE_POINTS))
        cooling = parse_curve_points(self._setup_data.get(CONF_COOLING_CURVE_POINTS, DEFAULT_COOLING_CURVE_POINTS))
        return self.async_show_form(
            step_id="custom_curve",
            data_schema=_curve_schema(heating, cooling, self._setup_data),
            errors=errors,
        )

    async def _async_finish_setup(self):
        """Create an entry with safe advanced defaults."""

        self._setup_data.setdefault(CONF_OUTDOOR_AVERAGING_HOURS, DEFAULT_OUTDOOR_AVERAGING_HOURS)
        self._setup_data.setdefault(CONF_INDOOR_START_DELTA, DEFAULT_INDOOR_START_DELTA)
        self._setup_data.setdefault(CONF_INDOOR_STOP_DELTA, DEFAULT_INDOOR_STOP_DELTA)
        self._setup_data.setdefault(CONF_INDOOR_SETTLING_HOURS, DEFAULT_INDOOR_SETTLING_HOURS)
        self._setup_data.setdefault(CONF_OPPOSITE_ENTITY_INTERLOCK, DEFAULT_OPPOSITE_ENTITY_INTERLOCK)
        title = self._setup_data.pop(CONF_NAME)
        await self.async_set_unique_id(f"{DOMAIN}_{title.lower().replace(' ', '_')}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=self._setup_data)


class HvacSetpointOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    @property
    def _options(self) -> dict[str, Any]:
        """Return the current config entry data and options."""

        return _options_from_entry(self.config_entry)

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Show options menu."""

        menu_options = ["linked_entities", "preset", "custom_curve", "control_behavior"]
        return self.async_show_menu(
            step_id="init",
            menu_options=menu_options,
        )

    async def async_step_linked_entities(self, user_input: dict[str, Any] | None = None):
        """Edit linked entities."""

        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_SENSOR_ONLY) and not (
                user_input.get(CONF_COOLING_CLIMATE) or user_input.get(CONF_HEATING_CLIMATE)
            ):
                errors["base"] = "missing_control_or_sensor_only"
            else:
                errors.update(_climate_mode_errors(self.hass, user_input))
                if not errors:
                    new_options = {**self.config_entry.options, **user_input}
                    for key in _LINKED_ENTITY_KEYS:
                        new_options[key] = user_input.get(key)
                    return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="linked_entities",
            data_schema=_linked_entities_schema(self.hass, self._options),
            errors=errors,
        )

    async def async_step_preset(self, user_input: dict[str, Any] | None = None):
        """Apply one profile to the entire building zone."""

        if user_input is not None:
            new_options = {**self.config_entry.options}
            if _apply_mode_presets(new_options, user_input):
                return await self.async_step_custom_curve()
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="preset",
            data_schema=_mode_preset_schema(self.hass, self._options, include_empty=False),
        )

    async def async_step_custom_curve(self, user_input: dict[str, Any] | None = None):
        """Edit heating, neutral zone and cooling together."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                heating_points, cooling_points = _points_from_slots(user_input)
                if float(user_input[CONF_HEATING_ON_THRESHOLD]) >= float(user_input[CONF_COOLING_ON_THRESHOLD]):
                    raise ValueError("overlapping_changeover")
            except ValueError:
                errors["base"] = "invalid_curve"
            else:
                new_options = {
                    **self.config_entry.options,
                    CONF_COOLING_CURVE_POINTS: cooling_points,
                    CONF_HEATING_CURVE_POINTS: heating_points,
                    CONF_PRESET: PRESET_CUSTOM,
                    CONF_COOLING_PRESET: PRESET_CUSTOM,
                    CONF_HEATING_PRESET: PRESET_CUSTOM,
                }
                heating_changeover = float(user_input[CONF_HEATING_ON_THRESHOLD])
                cooling_changeover = float(user_input[CONF_COOLING_ON_THRESHOLD])
                new_options.update(
                    {
                        CONF_HEATING_ON_THRESHOLD: heating_changeover,
                        CONF_HEATING_OFF_THRESHOLD: heating_changeover + 1.5,
                        CONF_COOLING_ON_THRESHOLD: cooling_changeover,
                        CONF_COOLING_OFF_THRESHOLD: cooling_changeover - 1.5,
                    }
                )
                return self.async_create_entry(title="", data=new_options)

        heating = parse_curve_points(self._options.get(CONF_HEATING_CURVE_POINTS, DEFAULT_HEATING_CURVE_POINTS))
        cooling = parse_curve_points(self._options.get(CONF_COOLING_CURVE_POINTS, DEFAULT_COOLING_CURVE_POINTS))
        return self.async_show_form(
            step_id="custom_curve",
            data_schema=_curve_schema(heating, cooling, self._options),
            errors=errors,
        )

    async def async_step_control_behavior(self, user_input: dict[str, Any] | None = None):
        """Edit outdoor smoothing and indoor-temperature demand."""

        if user_input is not None:
            new_options = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="control_behavior",
            data_schema=_control_behavior_schema(self._options),
        )
