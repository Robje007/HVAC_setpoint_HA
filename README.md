# HVAC Setpoint Curve

<img src="assets/logo.png" alt="HVAC Setpoint Curve logo" width="180">

[![Support on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/robje007)

Weather-compensated HVAC setpoint curves for Home Assistant.

This custom integration gives a home or small business one understandable HVAC profile: a heating line, a comfortable neutral zone, a cooling line, and outdoor temperatures for changing between seasons. It can expose the calculated targets for automations or control linked `climate` entities directly.

If HVAC Setpoint Curve is useful to you, you can [support its development on Ko-fi](https://ko-fi.com/robje007).

## Status

Version: [`1.2.1`](https://github.com/Robje007/HVAC_setpoint_HA/releases/tag/v1.2.1)

## Features

- UI setup, no YAML required.
- Multiple independent config entries for different rooms or zones.
- One combined 3-6 point comfort band containing heating and cooling limits.
- Simple Comfort and Eco building profiles based on common real-world room targets.
- A visible neutral zone prevents rapid switching between heating and cooling.
- One building-profile selector updates heating, cooling and outdoor changeover together.
- Persistent controller on/off switch for pausing automatic HVAC control while keeping manual control available.
- Automation-friendly night-mode switch with separate heating and cooling target corrections.
- Optional linked cooling and heating `climate` entities.
- Automatically selects `cool` or `heat` when a new session starts, then sends the calculated target temperature.
- Leaves linked HVAC equipment in its selected mode by default; an optional interlock can switch off a separate opposite entity.
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
- `number.<name>_cooling_on_threshold`
- `number.<name>_heating_on_threshold`
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

To customize behavior, open **Configure > Custom comfort band**. For each outdoor point, choose **Heat up to** and **Cool from**. The space between them is the neutral zone. On the same screen, choose below which outdoor temperature heating is allowed and above which temperature cooling is allowed. The normal Comfort and Eco profiles configure all of this automatically.

## Visual Curve Editor

The standard Home Assistant config flow can edit the comfort-band values, while the included Lovelace card shows their relationship much more clearly. Its full-width graph updates immediately when the simple values below it are changed:

```text
custom_components/hvac_setpoint_curve/www/hvac-setpoint-curve-card.js
```

After installing and restarting the integration:

1. In Home Assistant, go to **Settings > Dashboards > Resources**.
2. Add this JavaScript module resource:

```text
/hvac_setpoint_curve/hvac-setpoint-curve-card.js?v=1.2.1
```

3. Add a manual card:

```yaml
type: custom:hvac-setpoint-curve-card
entity: sensor.living_room_ac_curve_target_setpoint
title: Living room HVAC curve
```

The card shows heating in red, cooling in blue and the neutral changeover region between them. All values are edited and saved together, so there are no separate heating and cooling tabs to reconcile. A custom profile requires at least three outdoor points.

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

- Below the red line, heating demand can start when the outdoor heating limit permits it.
- Above the blue line, cooling demand can start when the outdoor cooling limit permits it.
- Between both lines, neither mode is requested; this is the comfort or neutral band.
- Between entered outdoor points, both limits are interpolated smoothly.

## Control Behavior and Thermal Inertia

The controller deliberately separates weather compensation from actual room demand:

- The current outdoor temperature calculates the target setpoint from the curve.
- A time-weighted outdoor-temperature average determines whether a new heating or cooling cycle may start. The default window is 3 hours; set it to 0 to disable averaging.
- When cooling demand starts, the configured cooling entity is automatically set to `cool` before the calculated target temperature is sent. Heating demand uses the same sequence with `heat`.
- Once a cycle is active, the climate mode remains available while the linked device's own thermostat cycles its compressor, burner, or valve.
- If residual heat or cold makes indoor temperature leave the target tolerance during stabilization, the timer resets. The linked thermostat can respond immediately because the climate mode was never switched off.
- Passing the target does not switch the climate mode off. The linked device's thermostat stops its compressor, burner, or valve itself and can restart it later to maintain the configured setpoint.

Indoor temperature source order for each mode:

1. Configured indoor-temperature override sensor, when available
2. `current_temperature` from that mode's linked climate entity
3. Existing outdoor-only hysteresis as a compatibility fallback when neither indoor value is available

Outdoor temperature source order:

1. Configured outdoor temperature sensor
2. First available `weather.*` temperature attribute

When an explicitly configured outdoor sensor is unavailable, the integration does not fall back to an indoor climate temperature. It leaves the current HVAC mode and target unchanged until a valid outdoor value returns.

Cooling:

- Starts when the averaged outdoor temperature is above **Cooling allowed above outdoor** and indoor temperature is at least 0.5 C above the blue cooling line by default.
- Once active, stays available through short weather changes. A hidden 1.5 C seasonal hysteresis prevents rapid switching around the chosen outdoor limit.

Heating:

- Starts when the averaged outdoor temperature is below **Heating allowed below outdoor** and indoor temperature is at least 0.5 C below the red heating line by default.
- Once active, stays available through short weather changes. A hidden 1.5 C seasonal hysteresis prevents rapid switching around the chosen outdoor limit.

The indoor start difference, target tolerance, and stabilization time are shared by heating and cooling and can be changed under **Configure > Thermal inertia and indoor demand**. Set stabilization time to 0 for immediate seasonal release once outdoor and indoor release conditions are both met. A room temperature beyond the target never releases the mode by itself: the integration continues updating the setpoint and lets the HVAC thermostat maintain it. For separate heating and cooling climate entities, each entity's own indoor measurement is used. The outdoor moving average is built while the integration is running; immediately after a restart it initially equals the current outdoor value and becomes representative as new time passes. A climate entity already in `heat` or `cool` is recognized as an active cycle after restart and receives a fresh full stabilization period.

Unavailable controlled climate entities are skipped for that update cycle and logged. If no valid outdoor temperature is available, linked equipment is left unchanged.

Before a target is sent, it is rounded to the linked climate entity's advertised `target_temp_step` (for example 0.5 or 1.0 C) and limited to its `min_temp` and `max_temp`. This applies independently to both heating and cooling entities. The target sensor continues to show the curve calculation at 0.1 C resolution.

Use the **Controller enabled** switch to pause or resume automatic HVAC control. Turning it off immediately stops this integration from sending mode and temperature commands and resets its heating/cooling active sensors, but deliberately leaves the linked HVAC equipment unchanged so it can be controlled manually. Curve and target-temperature calculations remain available, and the switch state persists across restarts.

Use the **Night mode** switch from a Home Assistant schedule, sleep routine, or presence automation. The number entities **Night mode: heat lower by** (default `1.5 C`) and **Night mode: cool higher by** (default `1.0 C`) can be adjusted directly beside the switch. The corrections are applied after the outdoor curve and humidity correction, while the original curve targets remain available as sensor attributes. Setting one to `0` disables the night adjustment for that mode.

The integration requires the heating outdoor limit to remain below the cooling limit and automatically adds safe seasonal hysteresis. One climate entity may safely be linked for both modes; it receives one non-conflicting command per update. For two separate entities, enable the interlock under **Configure > Advanced behavior** when they must never run together. A new heating demand then switches the cooler off first, and a new cooling demand switches the heater off first.

## FAQ

### Why use a curve instead of one fixed setpoint?

A curve lets the HVAC target adapt to outdoor conditions. For example, an energy-saving cooling curve can allow a higher indoor target during very hot weather, reducing compressor work while still avoiding sharp indoor/outdoor comfort swings.

### Can I use this without direct climate control?

Yes. Enable sensor-only mode. The integration will still create the target setpoint sensor and heating/cooling active binary sensors, but it will not call climate services or turn HVAC equipment on or off.

### Why does cooling remain enabled after the outdoor temperature falls at night?

This is intentional. Buildings retain heat after a hot day, and can warm up again after the compressor first stops. The controller therefore keeps the climate entity in cooling mode while its own thermostat handles these rebounds. The integration updates the target temperature but never sets the climate entity to `off`.

### Can profiles be edited?

Comfort and Eco are safe starting points. Editing the combined comfort band switches the building profile to Custom while keeping heating, cooling and changeover behavior together.

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
