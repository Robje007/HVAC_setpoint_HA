"""Constants for HVAC Setpoint Curve."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "hvac_setpoint_curve"
VERSION: Final = "0.3.0"

PLATFORMS: Final = ["sensor", "binary_sensor", "number", "select"]

CONF_NAME: Final = "name"
CONF_CURVE_POINTS: Final = "curve_points"
CONF_COOLING_CURVE_POINTS: Final = "cooling_curve_points"
CONF_HEATING_CURVE_POINTS: Final = "heating_curve_points"
CONF_PRESET: Final = "preset"
CONF_COOLING_CLIMATE: Final = "cooling_climate"
CONF_HEATING_CLIMATE: Final = "heating_climate"
CONF_OUTDOOR_TEMP_SENSOR: Final = "outdoor_temp_sensor"
CONF_HUMIDITY_SENSOR: Final = "humidity_sensor"
CONF_SENSOR_ONLY: Final = "sensor_only"
CONF_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE: Final = "turn_off_when_outdoor_unavailable"

DEFAULT_TURN_OFF_WHEN_OUTDOOR_UNAVAILABLE: Final = True

CONF_COOLING_ON_THRESHOLD: Final = "cooling_on_threshold"
CONF_COOLING_OFF_THRESHOLD: Final = "cooling_off_threshold"
CONF_HEATING_ON_THRESHOLD: Final = "heating_on_threshold"
CONF_HEATING_OFF_THRESHOLD: Final = "heating_off_threshold"

ATTR_OUTDOOR_TEMPERATURE_USED: Final = "outdoor_temperature_used"
ATTR_HUMIDITY_USED: Final = "humidity_used"
ATTR_ACTIVE_PRESET: Final = "active_preset"
ATTR_CURVE_POINTS: Final = "curve_points"
ATTR_COOLING_CURVE_POINTS: Final = "cooling_curve_points"
ATTR_HEATING_CURVE_POINTS: Final = "heating_curve_points"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"

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
    },
    "eco": {
        "name": "Eco / energy saving",
        "points": [
            {"outdoor_temp": -10.0, "setpoint": 20.0},
            {"outdoor_temp": 8.0, "setpoint": 19.0},
            {"outdoor_temp": 24.0, "setpoint": 25.0},
            {"outdoor_temp": 34.0, "setpoint": 27.0},
        ],
    },
    "rail_aggressive_cooling": {
        "name": "Rail-style aggressive cooling",
        "points": [
            {"outdoor_temp": 18.0, "setpoint": 23.0},
            {"outdoor_temp": 26.0, "setpoint": 21.0},
            {"outdoor_temp": 35.0, "setpoint": 20.0},
        ],
    },
}

DEFAULT_PRESET: Final = "comfort"
DEFAULT_CURVE_POINTS: Final = PRESETS[DEFAULT_PRESET]["points"]
DEFAULT_COOLING_CURVE_POINTS: Final = PRESETS["comfort"]["points"]
DEFAULT_HEATING_CURVE_POINTS: Final = [
    {"outdoor_temp": -10.0, "setpoint": 22.0},
    {"outdoor_temp": 0.0, "setpoint": 21.0},
    {"outdoor_temp": 12.0, "setpoint": 20.0},
    {"outdoor_temp": 18.0, "setpoint": 18.0},
]

SERVICE_SET_CURVE: Final = "set_curve"
SERVICE_RELOAD_PRESET: Final = "reload_preset"

CONF_ENTRY_ID: Final = "entry_id"
CONF_MODE: Final = "mode"
CONF_POINTS: Final = "points"

MODE_COOLING: Final = "cooling"
MODE_HEATING: Final = "heating"
MODE_BOTH: Final = "both"
