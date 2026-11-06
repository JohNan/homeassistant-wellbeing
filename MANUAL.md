# Electrolux Wellbeing - Manual

This text contains manual entries for non-obvious features of specific appliances.

## Robotic Vacuum Cleaners (RVC)

### PUREi9

Consumable sensors (Main Brush, Side Brush, Filter) show remaining life in
percent. The API only reports usage in square metres since the last reset;
the rated lifetimes (3000 m² for the main brush, 1000 m² for the side brush
and the filter) are not exposed by the API and were reverse engineered from
the percentages shown in the Electrolux app. Counters can only be reset from
the app.

The PUREi9.2 RVC supports the action `vacuum.send_command` with the command `clean_zones`, which allows for zone cleaning. The command expects two parameters: `map`, which is the name of a map (as named in the Wellbeing app), and `zones`, which is a list of zones to be cleaned. A zone in the list can either be the name of a zone to be cleaned (as a single string) or a dictionary containing the required key `zone` and an optional key `fan_speed` with values `power`, `quiet`, or `smart` to be used for the zone. If `fan_speed` is not specified, the default fan speed specified for that zone will be used.

#### Example 1

```
action: vacuum.send_command
data:
  command: clean_zones
  params:
    map: Downstairs
    zones:
      - Living room
      - Kitchen
target:
  entity_id: vacuum.r2d2_robotstatus
```

#### Example 2

```
action: vacuum.send_command
data:
  command: clean_zones
  params:
    map: Upstairs
    zones:
      - zone: Bedroom
        fan_speed: quiet
target:
  entity_id: vacuum.c3po_robotstatus
```
### Hygenic700

Room cleaning available in Hygenic700 (Gordias) robot vacuum cleaner. Command expect 'map_name' (from Electrolux app), room_name (from Electrolux app), 'sweep_mode' (0 (sweep only), 1 (mop & sweep)), 'vacuum_mode' (quiet, eco, standard, power), 'water_pump_rate', (off, low, medium, high), 'repetitions'. 

#### Example

```
action: vacuum.send_command
target:
  entity_id: vacuum.wellbeing_vacuum_state
data:
  params:
    map_name: Map1
    room_info:
      - room_name: Kitchen
        sweep_mode: 0
        vacuum_mode: standard
        water_pum_rate: "off"
        repetitions: 1
  command: clean_room
```

## Air purifiers

### Fuji (air purifier with heater)

The Electrolux "Fuji" (e.g. EP91-67UGA, `applianceType` `Fuji`,
`deviceType` `MULTI_AIR_PURIFIER`) is an air purifier with a built-in heater.
Besides the usual purifier entities (fan with `Auto`/`Manual`/`PowerOff`
presets, fan speed 1-9, PM1/PM2.5/PM10, TVOC, eCO2, temperature, humidity,
filter life, ionizer and safety lock switches) it exposes:

- `climate` **Heater**: `off` powers the appliance down, `fan_only` purifies
  without heating, `heat` turns the heater on. The target temperature range
  comes from the API (22-26 °C in steps of 2 on the EP91-67UGA). Setting a
  target first turns heating on, but note that the EP91-67UGA cloud rejects
  every `TemperatureTarget` command with "Capability not found" even though
  the capability is listed as writable, so on that model the target can only
  be changed on the appliance itself and Home Assistant reports an error.
- `switch` **UV Water Sterilisation** and **Quiet Fan**: these properties use
  `"on"`/`"off"` strings; the integration converts them. Quiet fan can only be
  changed while the work mode is `Auto`, and it is mutually exclusive with
  heating (the appliance disables one while the other is on).
- `select` **Louver Swing**, **PM Leading Mode** and **AQI Light**: the options
  are read from the capabilities (for example `off`/`swing`/`frontBack`/`front`).
  A select is only created when the API reports the property as writable.
- `sensor` **Air Quality** (`very_good` … `hazardous`), **Target Temperature**
  and **PM Leading Mode**; `binary_sensor` **Heating**, **Empty Water Tray**
  and an aggregated **Error** problem sensor whose `active_errors` attribute
  lists the raised `Err*` flags.
- `humidifier`: the firmware also reports `Humidification`/`HumidityTarget`.
  A humidifier entity is only created on variants whose capabilities allow
  writing `Humidification`; the EP91-67UGA does not have a humidifier.

Power is switched with the `executeCommand` capability (`on`/`off`) rather
than a `PowerOff` work mode, and `Workmode` commands must use the lower-case
values listed in the capabilities (`auto`, `manual`) even though the state
reports `Auto`/`Manual`; both are handled transparently.
