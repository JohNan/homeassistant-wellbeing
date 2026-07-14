# Electrolux Wellbeing - Manual

This text contains manual entries for non-obvious features of specific appliances.

## Robotic Vacuum Cleaners (RVC)

### Vacuum map camera

Robot vacuums whose appliance state reports dynamic map data (verified on the
PUREi9.2) get a camera entity showing the map of the latest cleaning session:
the covered area, the cleaning path, the charger and — while the robot is
moving — the robot itself. The image updates on every API update. Please note
that Electrolux's API provides the map data with quite a few minutes of delay,
i.e. much slower than the native Electrolux app. So consider it a map of what
the robot has cleaned, rather than where the robot is right now.

The camera can be used with a plain picture-entity card, or with
[Xiaomi Vacuum Map Card](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card),
which can be installed from [HACS](https://hacs.xyz) (search for "Xiaomi
Vacuum Map Card"). An example configuration, with tiles for status, battery,
fan speed, cleaned area and cleaning time (the latter two are only available
on appliances that report cleaning session data):

```yaml
type: custom:xiaomi-vacuum-map-card
entity: vacuum.your_robot
vacuum_platform: default
map_source:
  camera: camera.your_robot_map
calibration_source:
  camera: true
map_locked: true
tiles:
  - label: Status
    entity: vacuum.your_robot
    icon: mdi:robot-vacuum
  - label: Battery
    entity: sensor.your_robot_battery
    icon: mdi:battery
    unit: "%"
  - label: Fan speed
    entity: vacuum.your_robot
    attribute: fan_speed
    icon: mdi:fan
  - label: Cleaned area
    entity: sensor.your_robot_cleaned_area
    icon: mdi:texture-box
    unit: m²
  - label: Cleaning time
    entity: sensor.your_robot_cleaning_time
    icon: mdi:timer-outline
    unit: min
    multiplier: 0.01666667
    precision: 0
```

The camera exposes a `calibration_points` attribute mapping the vacuum
coordinate system (metres, persistent map frame) to image pixels, which the
card consumes via `calibration_source: camera: true`.

The map orientation can be adjusted with the "Vacuum map rotation" integration
option (degrees counter-clockwise), for example to match the orientation shown
in the Electrolux app.


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
