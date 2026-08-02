# HVAC Setpoint Curve

![HVAC Setpoint Curve logo](assets/logo.png)

Weather-compensated HVAC setpoint curves for Home Assistant.

This custom integration computes a target HVAC setpoint from a configurable outdoor temperature curve. It can expose the computed setpoint for automations, and optionally control linked heating and cooling `climate` entities with editable outdoor-temperature hysteresis thresholds.

## Status

Version: `0.3.0`

## Features

- UI setup, no YAML required.
- Multiple independent config entries for different rooms or zones.
- Configurable 3-6 point outdoor temperature to setpoint curve.
- Built-in presets: Comfort, Eco / energy saving, and Rail-style aggressive cooling.
- Editable live outdoor-temperature thresholds through `number` entities.
- Preset selection through a `select` entity. Applying a preset overwrites the current curve as a starting point.
- Optional linked cooling and heating `climate` entities.
- Optional outdoor temperature and outdoor humidity sensor links.
- Sensor-only mode for users who want the setpoint and active-state sensors but prefer to control HVAC with their own Home Assistant automations.

## Entities

Each config entry creates:

- `sensor.<name>_target_setpoint`
- `binary_sensor.<name>_cooling_active`
- `binary_sensor.<name>_heating_active`
- `number.<name>_cooling_on_threshold`
- `number.<name>_cooling_off_threshold`
- `number.<name>_heating_on_threshold`
- `number.<name>_heating_off_threshold`
- `select.<name>_preset`

## Brand Icon

Home Assistant 2026.3 and newer can show local custom integration brand assets from:

```text
custom_components/hvac_setpoint_curve/brand/icon.png
custom_components/hvac_setpoint_curve/brand/logo.png
```

After copying or updating these files, restart Home Assistant and hard-refresh the browser if the old icon is still cached.

The target setpoint sensor includes these attributes:

- `outdoor_temperature_used`
- `humidity_used`
- `active_preset`
- `curve_points`

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
3. Optionally choose outdoor temperature and outdoor humidity sensors.
4. Choose whether linked HVAC must be switched off if the outdoor temperature becomes unavailable. This safety option is enabled by default.
5. Pick a starting preset.
6. Confirm cooling and heating hysteresis thresholds for the outdoor temperature.

Required fields:

- Name
- At least one of: cooling climate entity, heating climate entity, or sensor-only mode

Optional fields:

- Cooling climate entity, if you only want heating or sensor-only mode
- Heating climate entity, if you only want cooling or sensor-only mode
- Outdoor temperature sensor
- Outdoor humidity sensor

Later, open **Configure** on the integration entry to:

- Change linked entities.
- Apply a preset.
- Create or edit one custom stook-/koellijn shared by heating and cooling.
- Edit thresholds.

To create a custom curve, open **Configure** and choose **Create or edit custom heating/cooling curve**. The same 3-6 points are used by both heating and cooling. Selecting `Custom` on the preset entity itself marks the active preset; Home Assistant select entities cannot open an editor screen.

Thresholds are also exposed as `number` entities so they can be changed directly from dashboards and automations.

## Visual Curve Editor

The standard Home Assistant config flow can edit curve points, but it cannot render a rich draggable graph. The integration package includes a Lovelace card for visual editing:

```text
custom_components/hvac_setpoint_curve/www/hvac-setpoint-curve-card.js
```

After installing and restarting the integration:

1. In Home Assistant, go to **Settings > Dashboards > Resources**.
2. Add this JavaScript module resource:

```text
/hvac_setpoint_curve/hvac-setpoint-curve-card.js?v=0.3.0
```

3. Add a manual card:

```yaml
type: custom:hvac-setpoint-curve-card
entity: sensor.living_room_ac_curve_target_setpoint
title: Living room HVAC curve
```

The card edits one custom curve shared by heating and cooling. Individual setpoints appear on the left and the live stook-/koellijn appears on the right. A custom curve requires at least three points.

The card saves changes through:

```text
hvac_setpoint_curve.set_curve
```

## Curve Example

A curve maps outdoor temperature to the desired setpoint:

| Outdoor temperature | Target setpoint |
| ---: | ---: |
| 18 C | 23 C |
| 26 C | 21 C |
| 35 C | 20 C |

Behavior:

- Below 18 C, the target setpoint stays flat at 23 C.
- Between 18 C and 26 C, the integration linearly interpolates between 23 C and 21 C.
- Between 26 C and 35 C, it interpolates between 21 C and 20 C.
- Above 35 C, it stays flat at 20 C.

## Control Behavior

Hysteresis is based on the outdoor temperature used by the integration, not on the indoor temperature reported by a climate entity.

Outdoor temperature source order:

1. Configured outdoor temperature sensor
2. First available `weather.*` temperature attribute

When an explicitly configured outdoor sensor is unavailable, the integration does not fall back to an indoor climate temperature. By default, direct HVAC control is switched off until a valid outdoor value returns. In **Configure > Linked entities and sensors**, this fail-safe can be disabled; the integration then leaves the current HVAC state unchanged while outdoor temperature is unavailable.

Cooling:

- Turns on when the outdoor temperature is above the cooling on threshold.
- Turns off when the outdoor temperature is below the cooling off threshold.

Heating:

- Turns on when the outdoor temperature is below the heating on threshold.
- Turns off when the outdoor temperature is above the heating off threshold.

Unavailable controlled climate entities are skipped for that update cycle and logged. If no valid outdoor temperature is available, direct control is switched off as a fail-safe.

The integration rejects reversed hysteresis ranges and requires a neutral band between heating and cooling. One climate entity may safely be linked for both modes; it receives one non-conflicting command per update.

## FAQ

### Why use a curve instead of one fixed setpoint?

A curve lets the HVAC target adapt to outdoor conditions. For example, an energy-saving cooling curve can allow a higher indoor target during very hot weather, reducing compressor work while still avoiding sharp indoor/outdoor comfort swings.

### Can I use this without direct climate control?

Yes. Enable sensor-only mode. The integration will still create the target setpoint sensor and heating/cooling active binary sensors, but it will not call climate services or turn HVAC equipment on or off.

### Can presets be edited?

Yes. Presets are only starting points. Editing curve points switches the active preset to custom.

## Development

Install the Home Assistant test dependencies and run the full suite:

```bash
python -m pip install -e ".[test]"
python -m pytest
```

Validation workflows are included for hassfest and HACS.

## License and contributions

This project is licensed under the [GNU General Public License v3.0](LICENSE) (`GPL-3.0-only`). You may use, modify, fork, and redistribute it under the GPLv3 conditions, including preserving the same license and providing the corresponding source when distributing modified versions.

Contributions are welcome through reviewed pull requests. Changes are merged only after approval by `@Robje007`; see [CONTRIBUTING.md](CONTRIBUTING.md).
