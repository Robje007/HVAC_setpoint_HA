# HVAC Setpoint Curve

<img src="assets/logo.png" alt="HVAC Setpoint Curve logo" width="180">

[![Support on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/robje007)

Weather-compensated HVAC setpoint curves for Home Assistant.

This custom integration gives a home or small business one automatic HVAC profile: a weather-compensated heating line, a comfortable neutral zone and a cooling line. Outdoor temperature shapes the comfort limits; indoor temperature automatically selects heating, neutral or cooling. It can expose the result for automations or directly control linked `climate` entities.

If HVAC Setpoint Curve is useful to you, you can [support its development on Ko-fi](https://ko-fi.com/robje007).

## Status

Version: [`2.0.0`](https://github.com/Robje007/HVAC_setpoint_HA/releases/tag/v2.0.0)

## Features

- UI setup, no YAML required.
- Multiple independent config entries for different rooms or zones.
- One combined 3-6 point comfort band containing heating and cooling limits.
- Simple Comfort and Eco building profiles based on common real-world room targets.
- A visible neutral zone prevents rapid switching between heating and cooling.
- One building-profile selector updates the complete automatic comfort band.
- Persistent controller on/off switch for pausing automatic HVAC control while keeping manual control available.
- Automation-friendly night-mode switch with separate heating and cooling target corrections.
- Optional linked cooling and heating `climate` entities.
- Automatically selects `cool` or `heat` when a new session starts, then sends the calculated target temperature.
- Sends mode and target commands only to the selected active side; an optional interlock can also switch off a separate opposite entity.
- Automatic indoor-temperature feedback from each linked climate entity's `current_temperature`.
- Optional outdoor temperature, indoor-temperature override, and outdoor humidity sensor links.
- Configurable time-weighted outdoor averaging, indoor demand tolerance, and stabilization time for building thermal inertia.
- Sensor-only mode for users who want the setpoint and active-state sensors but prefer to control HVAC with their own Home Assistant automations.

## Entities

Each config entry creates:

- `sensor.<name>_target_setpoint`
- `switch.<name>_controller_enabled`
- `binary_sensor.<name>_cooling_active`
- `binary_sensor.<name>_heating_active`
- `switch.<name>_night_mode`
- `number.<name>_cooling_night_offset`
- `number.<name>_heating_night_offset`
- `number.<name>_cooling_setpoint_correction` (when cooling control is linked)
- `select.<name>_building_profile`

## Brand Icon

Home Assistant 2026.3 and newer can show local custom integration brand assets from:

```text
custom_components/hvac_setpoint_curve/brand/icon.png
custom_components/hvac_setpoint_curve/brand/logo.png
```

After copying or updating these files, restart Home Assistant and hard-refresh the browser if the old icon is still cached.

The target setpoint sensor includes these attributes:

- `outdoor_temperature_used`
- `outdoor_temperature_average`
- `cooling_indoor_temperature_used`
- `cooling_indoor_temperature_source`
- `heating_indoor_temperature_used`
- `heating_indoor_temperature_source`
- `cooling_stabilizing`
- `heating_stabilizing`
- `humidity_used`
- `active_preset`
- `cooling_preset`
- `heating_preset`
- `curve_points`
- `cooling_curve_points`
- `heating_curve_points`

## Installation Via HACS

Requires Home Assistant `2025.12.0` or newer.

Repository: `https://github.com/Robje007/HVAC_setpoint_HA`

1. Open HACS in Home Assistant.
2. Choose **Integrations**.
3. Open the menu and choose **Custom repositories**.
4. Add `https://github.com/Robje007/HVAC_setpoint_HA`.
5. Set the category to **Integration**.
6. Install **HVAC Setpoint Curve**.
7. Restart Home Assistant.
8. Add the integration from **Settings > Devices & services > Add integration**.

## Configuration Walkthrough

During setup:

1. Enter a friendly name, such as `Living room AC curve`.
2. Choose the operating mode:
   - cooling only: select only a cooling climate entity
   - heating only: select only a heating climate entity
   - heating and cooling: select both climate entities
   - no direct control: enable sensor-only mode, which creates sensors only and does not send commands to HVAC
3. Optionally choose outdoor temperature and outdoor humidity sensors. The linked climate entity supplies the indoor temperature automatically through `current_temperature`; select a separate indoor sensor only when you want to override that measurement.
4. Choose **Comfort**, **Eco**, or **Custom**. Comfort and Eco are ready to use without engineering knowledge.

Required fields:

- Name
- At least one of: cooling climate entity, heating climate entity, or sensor-only mode

Optional fields:

- Cooling climate entity, if you only want heating or sensor-only mode
- Heating climate entity, if you only want cooling or sensor-only mode
- Outdoor temperature sensor
- Indoor temperature sensor override (normally unnecessary)
- Outdoor humidity sensor

Later, open **Configure** on the integration entry to:

- Change linked entities.
- Choose one building profile for the complete zone.
- Edit one custom comfort band containing heating, neutral and cooling behavior.
- Change advanced thermal-inertia behavior only when needed.

To customize behavior, open **Configure > Custom comfort band**. For each outdoor point, choose **Heat up to** and **Cool from**. The space between them is the automatic neutral zone. Comfort and Eco provide ready-to-use defaults.

## Visual Curve Editor

The standard Home Assistant config flow can edit the comfort-band values, while the included Lovelace card shows their relationship much more clearly. Its full-width graph updates immediately when the simple values below it are changed:

```text
custom_components/hvac_setpoint_curve/www/hvac-setpoint-curve-card.js
```

After installing and restarting the integration:

1. In Home Assistant, go to **Settings > Dashboards > Resources**.
2. Add this JavaScript module resource:

```text
/hvac_setpoint_curve/hvac-setpoint-curve-card.js?v=2.0.0
```

3. Add a manual card:

```yaml
type: custom:hvac-setpoint-curve-card
entity: sensor.living_room_ac_curve_target_setpoint
title: Living room HVAC curve
```

The card shows heating in red, cooling in blue and the automatic neutral comfort region between them. All values are edited and saved together. A custom profile requires at least three outdoor points.

The card saves changes through:

```text
hvac_setpoint_curve.set_profile
```

## Curve Example

A building profile maps outdoor temperature to a heating limit and a cooling limit:

| Outdoor temperature | Heat up to | Cool from |
| ---: | ---: | ---: |
| -10 C | 21.5 C | 24 C |
| 10 C | 21 C | 24 C |
| 20 C | 20 C | 24 C |
| 32 C | 18 C | 25 C |

Behavior:

- Below the red line, indoor temperature requests heating.
- Above the blue line, indoor temperature requests cooling.
- Between both lines, neither mode is requested; this is the comfort or neutral band.
- Between entered outdoor points, both limits are interpolated smoothly.

## Control Behavior and Thermal Inertia

The controller deliberately separates weather compensation from actual room demand:

Mode selection is automatic. Outdoor temperature is used to calculate the heating
and cooling comfort limits, while indoor temperature selects heating, the neutral
zone, or cooling. There are no separate outdoor start/stop thresholds.

- A time-weighted outdoor-temperature average calculates both comfort limits from the curves. The default window is 3 hours; set it to 0 to use the current outdoor value directly.
- Indoor temperature automatically chooses heating below the red limit, neutral between both limits, or cooling above the blue limit.
- When cooling demand starts, the configured cooling entity is automatically set to `cool` before the calculated target temperature is sent. Heating demand uses the same sequence with `heat`.
- Once a cycle is active, the climate mode remains available while the linked device's own thermostat cycles its compressor, burner, or valve.
- If residual heat or cold makes indoor temperature leave the target tolerance during stabilization, the timer resets. The linked thermostat can respond immediately because the climate mode was never switched off.
- Passing the target does not switch the climate mode off. The linked device's thermostat stops its compressor, burner, or valve itself and can restart it later to maintain the configured setpoint.

Indoor temperature source order for each mode:

1. Configured indoor-temperature override sensor, when available
2. `current_temperature` from that mode's linked climate entity
3. No demand when neither indoor value is available; automatic mode selection requires a valid indoor temperature

Outdoor temperature source order:

1. Configured outdoor temperature sensor
2. First available `weather.*` temperature attribute

When an explicitly configured outdoor sensor is unavailable, the integration does not fall back to an indoor climate temperature. It leaves the current HVAC mode and target unchanged until a valid outdoor value returns.

Cooling starts when indoor temperature is at least 0.5 C above the blue cooling limit by default. Heating starts when indoor temperature is at least 0.5 C below the red heating limit. Between the limits the system remains neutral.

The indoor start difference, target tolerance and stabilization time are shared by heating and cooling and can be changed under **Configure > Thermal inertia and indoor demand**. Set stabilization time to 0 for immediate release after reaching the target tolerance. For separate heating and cooling climate entities, each entity's own indoor measurement is used unless an override sensor is configured. The outdoor moving average starts at the current value after a restart and becomes representative as new samples arrive. A climate entity's existing `heat` or `cool` mode is never treated as proof of demand after restart; demand is recalculated from temperatures.

Unavailable controlled climate entities are skipped for that update cycle and logged. If no valid outdoor temperature is available, linked equipment is left unchanged.

Before a target is sent, it is rounded to the linked climate entity's advertised `target_temp_step` (for example 0.5 or 1.0 C) and limited to its `min_temp` and `max_temp`. This applies independently to both heating and cooling entities. The target sensor continues to show the curve calculation at 0.1 C resolution.

Air conditioners with a consistent setpoint deviation can be calibrated with the
`Cooling device setpoint correction` number entity. The correction is added only
to commands sent in cooling mode; for example, use `-1.0 °C` when the unit settles
1 °C warmer than requested. It does not alter the curve target or heating behavior.

Use the **Controller enabled** switch to pause or resume automatic HVAC control. Turning it off immediately stops this integration from sending mode and temperature commands and resets its heating/cooling active sensors, but deliberately leaves the linked HVAC equipment unchanged so it can be controlled manually. Curve and target-temperature calculations remain available, and the switch state persists across restarts.

Use the **Night mode** switch from a Home Assistant schedule, sleep routine, or presence automation. The number entities **Night mode: heat lower by** (default `1.5 C`) and **Night mode: cool higher by** (default `1.0 C`) can be adjusted directly beside the switch. The corrections are applied after the outdoor curve and humidity correction, while the original curve targets remain available as sensor attributes. Setting one to `0` disables the night adjustment for that mode.

The heating curve must remain below the cooling curve so a neutral band always exists. One climate entity may safely be linked for both modes; it receives one non-conflicting command per update. With two separate entities, automatic selection still controls only one side. Enable the interlock under **Configure > Advanced behavior** when the inactive opposite device must additionally be switched off.

## FAQ

### Why use a curve instead of one fixed setpoint?

A curve lets the HVAC target adapt to outdoor conditions. For example, an energy-saving cooling curve can allow a higher indoor target during very hot weather, reducing compressor work while still avoiding sharp indoor/outdoor comfort swings.

### Can I use this without direct climate control?

Yes. Enable sensor-only mode. The integration will still create the target setpoint sensor and heating/cooling active binary sensors, but it will not call climate services or turn HVAC equipment on or off.

### Why can cooling remain selected briefly after reaching its target?

The stabilization timer absorbs residual heat and cold so the controller does not rapidly switch modes. The linked thermostat can stop its compressor, burner or valve while the mode remains selected. Set stabilization time to `0` for immediate release.

### Can profiles be edited?

Comfort and Eco are safe starting points. Editing the combined comfort band switches the building profile to Custom while keeping automatic heating, neutral and cooling behavior together.

## Development

Install the Home Assistant test dependencies and run the full suite:

```bash
python -m pip install ".[test]"
python -m pytest
```

Validation workflows are included for hassfest and HACS.

## License and contributions

This project is licensed under the [GNU General Public License v3.0](LICENSE) (`GPL-3.0-only`). You may use, modify, fork, and redistribute it under the GPLv3 conditions, including preserving the same license and providing the corresponding source when distributing modified versions.

Contributions are welcome through reviewed pull requests. Changes are merged only after approval by `@Robje007`; see [CONTRIBUTING.md](CONTRIBUTING.md).
