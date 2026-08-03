# Changelog

## 0.3.1

- Automatically reads each linked climate entity's supported target-temperature step.
- Rounds heating and cooling commands to supported increments such as 0.5 or 1.0 C.
- Limits outgoing targets to the climate entity's advertised minimum and maximum temperatures.
- Keeps the curve and outdoor-humidity calculation visible at 0.1 C resolution while adapting only the command sent to the HVAC system.

## 0.3.0

- Replaces separate custom heating and cooling curves with one shared custom heating/cooling curve.
- Fixes blank Configure menu labels using the current Home Assistant `menu_options` translation structure.
- Updates the visual editor and `set_curve` service to save the shared curve to both modes.
- Migrates existing custom configurations to one shared curve.
- Prevents conflicting heat, cool, and off commands when both modes use the same climate entity.
- Validates climate capabilities and all hysteresis ranges before saving.
- Safely switches control off when the configured outdoor sensor becomes unavailable.
- Packages and serves the visual editor from inside the HACS integration directory.
- Replaces the separate heating and cooling target sensors with one “Target temperature from curve” sensor.
- Adds a setting that lets users choose whether HVAC is switched off or left unchanged when outdoor temperature is unavailable.

## 0.2.0

- Fixes the Configure button on Home Assistant 2025.12 and newer.
- Opens a curve editor when Custom is selected during setup or in the options flow.
- Requires 3-6 curve points and migrates existing two-point curves by adding an interpolated midpoint.
- Adds automatic Dutch and English entity names and Lovelace editor labels.
- Makes heating and cooling state names explain their live on/off thresholds.
- Clarifies target-temperature labels and that humidity is measured outdoors.

## 0.1.0

- Initial HACS-ready custom integration scaffold.
- Adds UI-only setup and options flow for linked entities, presets, curve points, and thresholds.
- Adds target setpoint sensor, heating/cooling active binary sensors, threshold number entities, and preset select entity.
- Adds curve interpolation and hysteresis unit tests.
- Adds separate cooling and heating curves.
- Adds a visual Lovelace curve editor card.
- Adds `hvac_setpoint_curve.set_curve` service for visual/editor-based curve updates.
- Hides cooling/heating threshold fields and mode entities when that mode is not configured.

## Migration Notes

- Existing version 1 and 2 entries are migrated automatically to the shared 3-6 point curve format.
- Assumption: config-flow curve editing remains a six-slot fallback editor because Home Assistant config flows do not support custom graph widgets. Rich visual editing is provided by the included Lovelace card.
