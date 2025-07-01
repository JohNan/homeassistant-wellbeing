# Electrolux Wellbeing - Manual

This text contains manual entries for non-obvious features of specific appliances.

## Robotic Vacuum Cleaners (RVC)

### PUREi9

The PUREi9.2 RVC supports the action `vacuum.send_command` with the command `clean_zones`, which allows for zone cleaning. The command expects two parameters: `map`, which is the name of a map (as named in the Wellbeing app), and `zones`, which is a list of zones to be cleaned. A zone in the list can either be the name of a zone to be cleaned (as a single string) or a dictionary containing the required key `name` and an optional key `mode` with values `power`, `quiet`, or `smart` to be used for the zone. If `mode` is not specified, the default power mode specified for that zone will be used.

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
  entity_id: r2d2_robotstatus
```

#### Example 2

```
action: vacuum.send_command
data:
  command: clean_zones
  params:
    map: Upstairs
    zones:
      - name: Bedroom
        mode: quiet
target:
  entity_id: c3po_robotstatus
```
