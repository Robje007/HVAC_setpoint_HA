# Changelog

## 2.0.0 - 2026-08-06

- Adds a signed cooling-device setpoint correction. Use `-1.0 °C` when an air conditioner settles 1 °C warmer than requested; heating targets and the displayed comfort target are unaffected.
- Only sends mode and target commands to the active heating or cooling side, so inactive Tado valves and air conditioners retain their own setpoints.
- Resolves simultaneous heating and cooling demand to one active building mode, also when separate climate entities are used without the optional power-off interlock.
- Replaces outdoor start/stop thresholds with automatic mode selection: outdoor temperature shapes the comfort band and indoor temperature chooses heating, neutral or cooling.
- Removes the four obsolete heating/cooling outdoor-threshold number entities and changeover inputs from the configuration and visual editor.
- Refreshes the integration branding with circular transparent logo and icon assets.

## 1.2.1 - 2026-08-05

- Replaces separate heating and cooling profile choices with one coherent building profile.
- Integrates heating, neutral-zone, cooling and outdoor changeover settings in one custom editor and graph.
- Provides simplified Comfort and Eco defaults suitable for homes and small commercial zones.
- Moves thermal inertia and interlock controls behind an Advanced settings entry.
- Migrates existing entries without discarding their curves or equipment links.
- Makes the combined heating/cooling graph full-width and prominent above the simple point editor.

## 1.2.0 - 2026-08-05

- Adds an automation-friendly night-mode switch with live number controls for independent heating and cooling target corrections.
- Exposes the unadjusted curve targets alongside the effective night-adjusted targets.
- Reuses one option-backed switch implementation for controller and night mode to keep the integration simpler.

## 1.1.0 - 2026-08-04

- Adds an opt-in interlock for separate heating and cooling entities, switching the opposite entity off before a new demand starts.
- Keeps shared heat-pump mode handling conflict-free and resolves overlapping interlocked demand before sending commands.
- Makes the visual curve editor wait for saves, report success or failure, warn before discarding edits, escape configured labels, and tolerate repeated setup and invalid graph bounds.
- Adds automated Ruff and pytest checks to GitHub Actions.
- Declares explicit setuptools package discovery and modern SPDX license metadata so development installs work reliably.
- Ignores Visual Studio workspace files and refreshes release documentation.
- Removes the unreferenced standalone demo and duplicate legacy integration icon while retaining the documented brand assets.

## 1.0.2 - 2026-08-03

- Stops sending `off` mode commands in every control path, including seasonal release and missing outdoor-temperature handling.
- Continues updating the curve target while the linked climate entity remains in its configured mode, leaving compressor or burner cycling to its thermostat.
- Removes the obsolete outdoor-sensor fail-safe option from setup; previously stored values are safely ignored.

## 1.0.1 - 2026-08-03

- Fixes cooling and heating being switched fully off when room temperature passes the target.
- Leaves the active climate mode available so the linked device's own thermostat can maintain its setpoint and restart automatically when needed.
- Removes the obsolete immediate-release overshoot setting from setup and options; previously stored values are safely ignored.

## 1.0.0 - 2026-08-03

- Renames the confusing Rail-style aggressive cooling preset to Aggressive cooling / Agressieve koeling without changing its internal key or curve.
- Adds independent cooling and heating profile selectors. Each selector appears only for its configured mode; Aggressive cooling remains cooling-only.
- Keeps optional linked-entity fields clearable instead of restoring a previous value as a hard default.
- Filters heating-only climate entities out of the cooling selector and cooling-only entities out of the heating selector.
- Uses each linked climate entity's `current_temperature` as automatic indoor-temperature feedback.
- Adds an optional separate indoor-temperature override for sensor-only setups or alternate room placement.
- Uses a configurable time-weighted outdoor average to gate new heating and cooling cycles.
- Keeps active cooling or heating available through short outdoor-temperature reversals until the indoor target is actually reached.
- Adds configurable indoor start hysteresis and target tolerance plus diagnostic temperature-source attributes.
- Adds a configurable stabilization period before releasing an active climate mode.
- Resets stabilization whenever residual heat or cold makes indoor temperature drift outside the target tolerance.
- Keeps the climate mode available during stabilization so the linked device's own thermostat can cycle again without waiting for outdoor start conditions.
- Adds a configurable immediate-release overshoot (1.0 C by default) for cases where the building is clearly cooled below or heated above target.
- Uses mode-specific Comfort and Eco curves so heating targets decrease logically as outdoor weather becomes milder.
- Applies high-humidity comfort correction in the correct direction: slightly cooler for cooling and warmer for heating.
- Resolves overlapping retained sessions on a shared heat pump in favor of its current mode instead of issuing a conflicting command.
- Shows the heating target while a heating-only installation is idle.
- Adds separate Cooling and Heating tabs to the visual curve editor and saves only the selected mode.

## 0.4.0

- Adds a persistent Controller enabled switch to pause and resume automatic control.
- Keeps target-temperature calculations available while the controller is disabled.
- Leaves linked HVAC equipment unchanged when disabling the controller so it remains available for manual control.
- Resets heating and cooling active-state sensors while automatic control is paused.

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
