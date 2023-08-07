# Electrolux Wellbeing

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

A custom component designed for [Home Assistant](https://www.home-assistant.io) with the capability to interact with the Electrolux devices connected to Wellbeing.

### Supported models

- Electrolux Well A5 Purifiers
    - WA51-302WT
    - WA51-302GY
    - WA51-303GY

- Electrolux Well A7 Purifiers
    - WA71-302GY
    - WA71-302DG
    - WA71-304GY
 
- Electrolux Pure A9 Purifiers
    - PA91-406GY
    - PA91-606DG
    - EHAW4010AG
    - EHAW6020AG

- AEG AX5 Air Purifiers
    - AX51-304WT
    
- AEG AX7 Air Purifiers
    - AX71-304GY
    - AX71-304DG
    
- AEG AX9 Air Purifiers
    - AX91-404GY
    - AX91-404DG
    - AX91-405DG
    - AX91-604GY
    - AX91-604DG

### Install with HACS (recommended)
Do you you have [HACS][hacs] installed? Just search for Electrolux Wellbeing and install it direct from HACS. HACS will keep track of updates and you can easily upgrade this integration to latest version.

### Manual Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `wellbeing`.
4. Download _all_ the files from the `custom_components/wellbeing/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Electrolux Wellbeing"


Contributions are welcome!

---

[buymecoffee]: https://www.buymeacoffee.com/JohNan
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/JohNan/homeassistant-wellbeing.svg?style=for-the-badge
[commits]: https://github.com/JohNan/homeassistant-wellbeing/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/JohNan/homeassistant-wellbeing.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40JohNan-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/JohNan/homeassistant-wellbeing.svg?style=for-the-badge
[releases]: https://github.com/JohNan/homeassistant-wellbeing/releases
[user_profile]: https://github.com/JohNan
