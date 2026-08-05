"""Constants for HVAC Setpoint Curve."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "hvac_setpoint_curve"
VERSION: Final = "1.2.0"

PLATFORMS: Final = ["sensor", "binary_sensor", "number", "select", "switch"]

CONF_NAME: Final = "name"
CONF_CURVE_POINTS: Final = "curve_points"
CONF_COOLING_CURVE_POINTS: Final = "cooling_curve_points"
CONF_HEATING_CURVE_POINTS: Final = "heating_curve_points"
CONF_PRESET: Final = "preset"
CONF_COOLING_PRESET: Final = "cooling_preset"
CONF_HEATING_PRESET: Final = "heating_preset"
CONF_COOLING_CLIMATE: Final = "cooling_climate"
CONF_HEATING_CLIMATE: Final = "heating_climate"
CONF_OUTDOOR_TEMP_SENSOR: Final = "outdoor_temp_sensor"
CONF_INDOOR_TEMP_SENSOR: Final = "indoor_temp_sensor"
CONF_HUMIDITY_SENSOR: Final = "humidity_sensor"
CONF_SENSOR_ONLY: Final = "sensor_only"
CONF_CONTROLLER_ENABLED: Final = "controller_enabled"
CONF_NIGHT_MODE: Final = "night_mode"
CONF_COOLING_NIGHT_OFFSET: Final = "cooling_night_offset"
CONF_HEATING_NIGHT_OFFSET: Final = "heating_night_offset"
CONF_OPPOSITE_ENTITY_INTERLOCK: Final = "opposite_entity_interlock"

DEFAULT_CONTROLLER_ENABLED: Final = True
DEFAULT_NIGHT_MODE: Final = False
DEFAULT_COOLING_NIGHT_OFFSET: Final = 1.0
DEFAULT_HEATING_NIGHT_OFFSET: Final = -1.5
DEFAULT_OPPOSITE_ENTITY_INTERLOCK: Final = False
CONF_OUTDOOR_AVERAGING_HOURS: Final = "outdoor_averaging_hours"
CONF_INDOOR_START_DELTA: Final = "indoor_start_delta"
CONF_INDOOR_STOP_DELTA: Final = "indoor_stop_delta"
CONF_INDOOR_SETTLING_HOURS: Final = "indoor_settling_hours"
DEFAULT_OUTDOOR_AVERAGING_HOURS: Final = 3.0
DEFAULT_INDOOR_START_DELTA: Final = 0.5
DEFAULT_INDOOR_STOP_DELTA: Final = 0.2
DEFAULT_INDOOR_SETTLING_HOURS: Final = 2.0

CONF_COOLING_ON_THRESHOLD: Final = "cooling_on_threshold"
CONF_COOLING_OFF_THRESHOLD: Final = "cooling_off_threshold"
CONF_HEATING_ON_THRESHOLD: Final = "heating_on_threshold"
CONF_HEATING_OFF_THRESHOLD: Final = "heating_off_threshold"

ATTR_OUTDOOR_TEMPERATURE_USED: Final = "outdoor_temperature_used"
ATTR_OUTDOOR_TEMPERATURE_AVERAGE: Final = "outdoor_temperature_average"
ATTR_COOLING_INDOOR_TEMPERATURE_USED: Final = "cooling_indoor_temperature_used"
ATTR_HEATING_INDOOR_TEMPERATURE_USED: Final = "heating_indoor_temperature_used"
ATTR_COOLING_INDOOR_TEMPERATURE_SOURCE: Final = "cooling_indoor_temperature_source"
ATTR_HEATING_INDOOR_TEMPERATURE_SOURCE: Final = "heating_indoor_temperature_source"
ATTR_COOLING_STABILIZING: Final = "cooling_stabilizing"
ATTR_HEATING_STABILIZING: Final = "heating_stabilizing"
ATTR_HUMIDITY_USED: Final = "humidity_used"
ATTR_ACTIVE_PRESET: Final = "active_preset"
ATTR_COOLING_PRESET: Final = "cooling_preset"
ATTR_HEATING_PRESET: Final = "heating_preset"
ATTR_CURVE_POINTS: Final = "curve_points"
ATTR_COOLING_CURVE_POINTS: Final = "cooling_curve_points"
ATTR_HEATING_CURVE_POINTS: Final = "heating_curve_points"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_NIGHT_MODE: Final = "night_mode"
ATTR_COOLING_CURVE_SETPOINT: Final = "cooling_curve_setpoint"
ATTR_HEATING_CURVE_SETPOINT: Final = "heating_curve_setpoint"

PRESET_CUSTOM: Final = "custom"
PRESET_EMPTY: Final = "empty"

DEFAULT_COOLING_ON_THRESHOLD: Final = 24.0
DEFAULT_COOLING_OFF_THRESHOLD: Final = 22.5
DEFAULT_HEATING_ON_THRESHOLD: Final = 18.0
DEFAULT_HEATING_OFF_THRESHOLD: Final = 19.5

MIN_CURVE_POINTS: Final = 3
MAX_CURVE_POINTS: Final = 6

TEMPERATURE_MIN: Final = -30.0
TEMPERATURE_MAX: Final = 45.0
SETPOINT_MIN: Final = 5.0
SETPOINT_MAX: Final = 35.0
THRESHOLD_MIN: Final = 5.0
THRESHOLD_MAX: Final = 35.0

PRESETS: Final = {
    "comfort": {
        "name": "Comfort",
        "points": [
            {"outdoor_temp": -10.0, "setpoint": 22.0},
            {"outdoor_temp": 5.0, "setpoint": 21.0},
            {"outdoor_temp": 20.0, "setpoint": 23.0},
            {"outdoor_temp": 32.0, "setpoint": 25.0},
        ],
        "heating_points": [
            {"outdoor_temp": -10.0, "setpoint": 22.0},
            {"outdoor_temp": 0.0, "setpoint": 21.0},
            {"outdoor_temp": 12.0, "setpoint": 20.0},
            {"outdoor_temp": 18.0, "setpoint": 18.0},
        ],
    },
    "eco": {
        "name": "Eco / energy saving",
        "points": [
            {"outdoor_temp": -10.0, "setpoint": 20.0},
            {"outdoor_temp": 8.0, "setpoint": 19.0},
            {"outdoor_temp": 24.0, "setpoint": 25.0},
            {"outdoor_temp": 34.0, "setpoint": 27.0},
        ],
        "heating_points": [
            {"outdoor_temp": -10.0, "setpoint": 20.0},
            {"outdoor_temp": 0.0, "setpoint": 19.5},
            {"outdoor_temp": 12.0, "setpoint": 18.5},
            {"outdoor_temp": 18.0, "setpoint": 17.0},
        ],
    },
    "rail_aggressive_cooling": {
        "name": "Aggressive cooling",
        "points": [
            {"outdoor_temp": 18.0, "setpoint": 23.0},
            {"outdoor_temp": 26.0, "setpoint": 21.0},
            {"outdoor_temp": 35.0, "setpoint": 20.0},
        ],
    },
}


def preset_name(preset_key: str, language: str | None = None) -> str:
    """Return the localized visible name for a built-in preset."""

    is_dutch = bool(language and language.lower().startswith("nl"))
    if preset_key == PRESET_CUSTOM:
        return "Aangepast" if is_dutch else "Custom"
    if preset_key == PRESET_EMPTY:
        return "Leeg beginnen / aangepast" if is_dutch else "Start empty / custom"
    if is_dutch and preset_key == "rail_aggressive_cooling":
        return "Agressieve koeling"
    if is_dutch and preset_key == "eco":
        return "Eco / energiebesparing"
    return str(PRESETS[preset_key]["name"])


def preset_curve(preset_key: str, mode: str) -> list[dict[str, float]]:
    """Return mode-appropriate points for a built-in preset."""

    preset = PRESETS[preset_key]
    if mode == "heating" and "heating_points" in preset:
        return list(preset["heating_points"])
    return list(preset["points"])


DEFAULT_PRESET: Final = "comfort"
DEFAULT_CURVE_POINTS: Final = PRESETS[DEFAULT_PRESET]["points"]
DEFAULT_COOLING_CURVE_POINTS: Final = PRESETS["comfort"]["points"]
DEFAULT_HEATING_CURVE_POINTS: Final = PRESETS[DEFAULT_PRESET]["heating_points"]

SERVICE_SET_CURVE: Final = "set_curve"
SERVICE_RELOAD_PRESET: Final = "reload_preset"

CONF_ENTRY_ID: Final = "entry_id"
CONF_MODE: Final = "mode"
CONF_POINTS: Final = "points"

MODE_COOLING: Final = "cooling"
MODE_HEATING: Final = "heating"
MODE_BOTH: Final = "both"
