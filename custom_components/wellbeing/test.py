sweepMode: 0, 1
vacuumMode = quiet, energySaving, standard, powerful
waterPumpRate  = off, low, medium, high
cleaningType = vacuum, mop, vacuumAndMop, vacuumFirstThenMop
map_name: Map1
room_info:
  - room_name: Izu
    vacuum_mode: standard
    water_pump_rate: "off"
    repetitions: 1

params = {
        "map_command": "selectRoomsClean",
        "map_name": 'Map1',
        "room_info": [
            {
                "room_name": "Izu2",
                "sweep_mode": 0,
                "cleaning_type": "vacuum",
                "vacuum_mode": "standard",
                "water_pump_rate": "off",
                "repetitions": 1,
            },
            {
                "room_name": "Boldi",
                "sweep_mode": 0,
                "cleaning_type": "vacuum",
                "vacuum_mode": "standard",
                "water_pump_rate": "off",
                "repetitions": 1,
            }
        ]
    }

room_playload = {'mapCommand': 'selectRoomsClean', 
                 'mapId' : 1000,
                 'type': 1}
room_info = []
for room in params['room_info']:
  #room_id = next((r['id'] for r in api_map.data.get("rooms", []) if r['name'] == room['room_name']), None)
  room_id = 10
  room_info.append(
    {'roomId' : room_id,
     'sweepMode' : room['sweep_mode'],
     'vacuumMode' : room['vacuum_mode'],
     'waterPumpRate' : room['water_pump_rate'],
     'numberOfCleaningRepetitions': room['repetitions']}
  )
room_playload['roomInfo'] = room_info
#----
FAN_SPEEDS_700SERIES = {
    "quiet": "quiet",
    "eco": "energySaving",
    "standard": "standard",
    "power": "powerful",
}

vacuum_mode = FAN_SPEEDS_700SERIES.get('eco')
isinstance(vacuum_mode, str)

isinstance(1, int)