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
    DEFAULT_CURVE_POINTS,
    DEFAULT_HEATING_CURVE_POINTS,
    DEFAULT_HEATING_OFF_THRESHOLD,
    DEFAULT_HEATING_ON_THRESHOLD,
    DEFAULT_PRESET,
    DEFAULT_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE,
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
    THRESHOLD_MAX,
    THRESHOLD_MIN,
)
from .curve import CurvePoint, parse_curve_points, serialize_curve_points
from .validation import threshold_error

_LINKED_ENTITY_KEYS = (
    CONF_COOLING_CLIMATE,
    CONF_HEATING_CLIMATE,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_HUMIDITY_SENSOR,
)


def _entity_selector(domain: str) -> selector.EntitySelector:
    """Create an entity selector for a domain."""

    return selector.EntitySelector(selector.EntitySelectorConfig(domain=domain))


def _preset_options(include_empty: bool = True) -> list[dict[str, str]]:
    """Return select options for presets."""

    options = [{"value": key, "label": preset["name"]} for key, preset in PRESETS.items()]
    if include_empty:
        options.append({"value": PRESET_EMPTY, "label": "Start empty / custom"})
    else:
        options.append({"value": PRESET_CUSTOM, "label": "Create or edit custom curve"})
    return options


def _optional_entity_field(key: str, label_options: dict[str, Any]) -> vol.Optional:
    """Create an optional field without injecting None as a default."""

    if label_options.get(key):
        return vol.Optional(key, default=label_options[key])
    return vol.Optional(key)


def _threshold_schema(options: dict[str, Any]) -> vol.Schema:
    """Build the threshold form schema."""

    fields: dict[vol.Marker, Any] = {}
    if _cooling_enabled(options):
        fields.update(
            {
                vol.Required(
                    CONF_COOLING_ON_THRESHOLD,
                    default=options.get(CONF_COOLING_ON_THRESHOLD, DEFAULT_COOLING_ON_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=THRESHOLD_MIN,
                        max=THRESHOLD_MAX,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="°C",
                    )
                ),
                vol.Required(
                    CONF_COOLING_OFF_THRESHOLD,
                    default=options.get(CONF_COOLING_OFF_THRESHOLD, DEFAULT_COOLING_OFF_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=THRESHOLD_MIN,
                        max=THRESHOLD_MAX,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="°C",
                    )
                ),
            }
        )
    if _heating_enabled(options):
        fields.update(
            {
                vol.Required(
                    CONF_HEATING_ON_THRESHOLD,
                    default=options.get(CONF_HEATING_ON_THRESHOLD, DEFAULT_HEATING_ON_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=THRESHOLD_MIN,
                        max=THRESHOLD_MAX,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="°C",
                    )
                ),
                vol.Required(
                    CONF_HEATING_OFF_THRESHOLD,
                    default=options.get(CONF_HEATING_OFF_THRESHOLD, DEFAULT_HEATING_OFF_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=THRESHOLD_MIN,
                        max=THRESHOLD_MAX,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="°C",
                    )
                ),
            }
        )
    return vol.Schema(fields)


def _cooling_enabled(options: dict[str, Any]) -> bool:
    """Return whether cooling fields should be visible."""

    return bool(options.get(CONF_COOLING_CLIMATE) or options.get(CONF_SENSOR_ONLY))


def _heating_enabled(options: dict[str, Any]) -> bool:
    """Return whether heating fields should be visible."""

    return bool(options.get(CONF_HEATING_CLIMATE) or options.get(CONF_SENSOR_ONLY))


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


def _linked_entities_schema(options: dict[str, Any], *, include_name: bool = False) -> vol.Schema:
    """Build linked entities form schema."""

    fields: dict[vol.Marker, Any] = {}
    if include_name:
        fields[vol.Required(CONF_NAME, default=options.get(CONF_NAME, "Living room AC curve"))] = str

    fields.update(
        {
            _optional_entity_field(CONF_COOLING_CLIMATE, options): _entity_selector("climate"),
            _optional_entity_field(CONF_HEATING_CLIMATE, options): _entity_selector("climate"),
            _optional_entity_field(CONF_OUTDOOR_TEMP_SENSOR, options): _entity_selector("sensor"),
            _optional_entity_field(CONF_HUMIDITY_SENSOR, options): _entity_selector("sensor"),
            vol.Required(CONF_SENSOR_ONLY, default=options.get(CONF_SENSOR_ONLY, False)): selector.BooleanSelector(),
            vol.Required(
                CONF_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE,
                default=options.get(
                    CONF_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE,
                    DEFAULT_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE,
                ),
            ): selector.BooleanSelector(),
        }
    )
    return vol.Schema(fields)


def _curve_schema(points: list[CurvePoint] | None = None) -> vol.Schema:
    """Build a fixed-slot curve editor schema."""

    points = points or parse_curve_points(DEFAULT_CURVE_POINTS)
    fields: dict[vol.Marker, Any] = {
        vol.Required("point_count", default=len(points)): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=MIN_CURVE_POINTS,
                max=MAX_CURVE_POINTS,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
            )
        )
    }

    for index in range(MAX_CURVE_POINTS):
        point = points[index] if index < len(points) else None
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
        setpoint_key = f"setpoint_{index + 1}"
        setpoint_marker = vol.Optional(setpoint_key, default=point.setpoint) if point else vol.Optional(setpoint_key)
        fields[setpoint_marker] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=SETPOINT_MIN,
                max=SETPOINT_MAX,
                step=0.1,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="°C",
            )
        )
    return vol.Schema(fields)


def _points_from_slots(user_input: dict[str, Any]) -> list[dict[str, float]]:
    """Convert fixed-slot form data into validated curve points."""

    point_count = int(user_input["point_count"])
    points = []
    for index in range(point_count):
        outdoor = user_input.get(f"outdoor_temp_{index + 1}")
        setpoint = user_input.get(f"setpoint_{index + 1}")
        if outdoor is None or setpoint is None:
            raise ValueError("missing_point")
        points.append(CurvePoint(float(outdoor), float(setpoint)))
    return serialize_curve_points(parse_curve_points(points))


def _options_from_entry(entry: config_entries.ConfigEntry) -> dict[str, Any]:
    """Merge entry data and options."""

    return {**entry.data, **entry.options}


class HvacSetpointConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 3

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
            data_schema=_linked_entities_schema(self._setup_data, include_name=True),
            errors=errors,
        )

    async def async_step_preset(self, user_input: dict[str, Any] | None = None):
        """Choose a starting preset."""

        if user_input is not None:
            preset = user_input[CONF_PRESET]
            self._setup_data[CONF_PRESET] = preset
            if preset in PRESETS:
                self._setup_data[CONF_CURVE_POINTS] = PRESETS[preset]["points"]
                self._setup_data[CONF_COOLING_CURVE_POINTS] = PRESETS[preset]["points"]
                self._setup_data[CONF_HEATING_CURVE_POINTS] = DEFAULT_HEATING_CURVE_POINTS
            else:
                self._setup_data[CONF_CURVE_POINTS] = DEFAULT_CURVE_POINTS
                self._setup_data[CONF_COOLING_CURVE_POINTS] = DEFAULT_COOLING_CURVE_POINTS
                self._setup_data[CONF_HEATING_CURVE_POINTS] = DEFAULT_HEATING_CURVE_POINTS
                self._setup_data[CONF_PRESET] = PRESET_CUSTOM
                return await self.async_step_custom_curve()
            return await self.async_step_thresholds()

        return self.async_show_form(
            step_id="preset",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRESET, default=DEFAULT_PRESET): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_preset_options(include_empty=True),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_custom_curve(self, user_input: dict[str, Any] | None = None):
        """Create one shared initial heating and cooling curve."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                points = _points_from_slots(user_input)
            except ValueError:
                errors["base"] = "invalid_curve"
            else:
                self._setup_data[CONF_CURVE_POINTS] = points
                self._setup_data[CONF_COOLING_CURVE_POINTS] = points
                self._setup_data[CONF_HEATING_CURVE_POINTS] = points
                return await self.async_step_thresholds()

        points = parse_curve_points(self._setup_data.get(CONF_CURVE_POINTS, DEFAULT_CURVE_POINTS))
        return self.async_show_form(
            step_id="custom_curve",
            data_schema=_curve_schema(points),
            errors=errors,
        )

    async def async_step_thresholds(self, user_input: dict[str, Any] | None = None):
        """Configure initial thresholds."""

        errors: dict[str, str] = {}
        if user_input is not None:
            candidate = {**self._setup_data, **user_input}
            error = threshold_error(
                candidate,
                cooling_enabled=_cooling_enabled(candidate),
                heating_enabled=_heating_enabled(candidate),
            )
            if error:
                errors["base"] = error
            else:
                self._setup_data.update(user_input)
                title = self._setup_data.pop(CONF_NAME)
                await self.async_set_unique_id(f"{DOMAIN}_{title.lower().replace(' ', '_')}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data=self._setup_data)

        return self.async_show_form(
            step_id="thresholds",
            data_schema=_threshold_schema(self._setup_data),
            errors=errors,
        )


class HvacSetpointOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    @property
    def _options(self) -> dict[str, Any]:
        """Return the current config entry data and options."""

        return _options_from_entry(self.config_entry)

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Show options menu."""

        menu_options = ["linked_entities", "preset", "custom_curve"]
        menu_options.append("thresholds")
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
            data_schema=_linked_entities_schema(self._options),
            errors=errors,
        )

    async def async_step_preset(self, user_input: dict[str, Any] | None = None):
        """Apply a built-in preset."""

        if user_input is not None:
            preset = user_input[CONF_PRESET]
            if preset == PRESET_CUSTOM:
                return await self.async_step_custom_curve()

            new_options = {**self.config_entry.options, CONF_PRESET: preset}
            if preset in PRESETS:
                new_options[CONF_CURVE_POINTS] = PRESETS[preset]["points"]
                new_options[CONF_COOLING_CURVE_POINTS] = PRESETS[preset]["points"]
                new_options.setdefault(CONF_HEATING_CURVE_POINTS, DEFAULT_HEATING_CURVE_POINTS)
            elif preset == PRESET_EMPTY:
                new_options[CONF_CURVE_POINTS] = DEFAULT_CURVE_POINTS
                new_options[CONF_COOLING_CURVE_POINTS] = DEFAULT_COOLING_CURVE_POINTS
                new_options[CONF_HEATING_CURVE_POINTS] = DEFAULT_HEATING_CURVE_POINTS
                new_options[CONF_PRESET] = PRESET_CUSTOM
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="preset",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PRESET,
                        default=self._options.get(CONF_PRESET, PRESET_CUSTOM),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_preset_options(include_empty=False),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_custom_curve(self, user_input: dict[str, Any] | None = None):
        """Edit one custom curve shared by heating and cooling."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                points = _points_from_slots(user_input)
            except ValueError:
                errors["base"] = "invalid_curve"
            else:
                new_options = {
                    **self.config_entry.options,
                    CONF_CURVE_POINTS: points,
                    CONF_COOLING_CURVE_POINTS: points,
                    CONF_HEATING_CURVE_POINTS: points,
                    CONF_PRESET: PRESET_CUSTOM,
                }
                return self.async_create_entry(title="", data=new_options)

        points = parse_curve_points(
            self._options.get(CONF_CURVE_POINTS) or self._options.get(CONF_COOLING_CURVE_POINTS) or DEFAULT_CURVE_POINTS
        )
        return self.async_show_form(
            step_id="custom_curve",
            data_schema=_curve_schema(points),
            errors=errors,
        )

    async def async_step_thresholds(self, user_input: dict[str, Any] | None = None):
        """Edit thresholds."""

        errors: dict[str, str] = {}
        if user_input is not None:
            candidate = {**self._options, **user_input}
            error = threshold_error(
                candidate,
                cooling_enabled=_cooling_enabled(candidate),
                heating_enabled=_heating_enabled(candidate),
            )
            if error:
                errors["base"] = error
            else:
                new_options = {**self.config_entry.options, **user_input}
                return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="thresholds",
            data_schema=_threshold_schema(self._options),
            errors=errors,
        )
