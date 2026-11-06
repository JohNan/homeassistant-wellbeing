"""Sample API Client."""

import asyncio
import logging
from enum import StrEnum

import voluptuous as vol
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.vacuum import Segment
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    Platform,
    UnitOfDensity,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.typing import UNDEFINED
from pyelectroluxgroup.api import ElectroluxHubAPI
from pyelectroluxgroup.appliance import Appliance as ApiAppliance

FILTER_TYPE = {
    48: "BREEZE Complete air filter",
    49: "CLEAN Ultrafine particle filter",
    51: "CARE Ultimate protect filter",
    55: "Breathe 400 filter",
    64: "Breeze 360 filter",
    65: "Clean 360 Ultrafine particle filter",
    66: "Protect 360 filter",
    67: "Breathe 360 filter",
    68: "Fresh 360 filter",
    96: "Breeze 360 filter",
    99: "Breeze 360 filter",
    100: "Fresh 360 filter",
    192: "FRESH Odour protect filter",
    194: "FRESH Odour protect filter",
    0: "Filter",
}

# Schemas for definition of an interactive map and its zones for the PUREi9 vacuum cleaner.
FAN_SPEEDS_PUREI9 = {
    "eco": True,
    "power": False,
}

FAN_SPEEDS_PUREI92 = {
    "quiet": 1,
    "smart": 2,
    "power": 3,
}

INTERACTIVE_MAP_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required("zone"): str,
        vol.Optional("fan_speed"): vol.In(list(FAN_SPEEDS_PUREI92.keys())),
    }
)


def validate_vacuum_zone_entry(value):
    """Helper to validate a zone entry for INTERACTIVE_MAP_SCHEMA."""
    """Converts a string to a dictionary with a single 'zone' key for briefer default params."""
    if isinstance(value, str):
        return {"zone": value}
    if isinstance(value, dict):
        return INTERACTIVE_MAP_ZONE_SCHEMA(value)
    raise vol.Invalid("Zone entry must be a string or a dict with a 'zone' key")


INTERACTIVE_MAP_SCHEMA = vol.Schema(
    {
        vol.Required("map"): str,
        vol.Required("zones"): [validate_vacuum_zone_entry],
    }
)

FAN_SPEEDS_700SERIES = {
    "quiet": "quiet",
    "eco": "energySaving",
    "standard": "standard",
    "power": "powerful",
}

WATER_PUMP_RATES_700SERIES = ["off", "low", "medium", "high"]


_LOGGER: logging.Logger = logging.getLogger(__package__)


class Model(StrEnum):
    Muju = "Muju"
    WELLA5 = "WELLA5"
    WELLA7 = "WELLA7"
    PUREA9 = "PUREA9"
    AX5 = "AX5"
    AX7 = "AX7"
    AX9 = "AX9"
    PUREi9 = "PUREi9"
    PM700 = "Verbier"  # "PUREMULTI700"
    Robot700series = "700series"  # 700series vacuum robot series
    UltimateHome700 = "UltimateHome 700"  # Dehumidifier
    VacuumHygienic700 = "Gordias"  # HYGIENIC700
    Cybele = "Cybele"
    COMFORT600 = "COMFORT600"
    AZUL = "Azul"
    FUJI = (
        "Fuji"  # Air purifier with heater and humidifier (e.g. Taiwan 冷暖空氣清淨機)
    )


class WorkMode(StrEnum):
    OFF = "PowerOff"
    MANUAL = "Manual"
    UNDEFINED = "Undefined"
    SMART = "Smart"
    QUITE = "Quiet"
    AUTO = "Auto"
    # Virtual preset for purifiers with a heater (Heating property, e.g. Fuji).
    HEAT = "Heat"


class LouverSwingMode(StrEnum):
    OFF = "off"
    NARROW = "narrow"
    WIDE = "wide"
    NATURAL_BREEZE = "naturalbreeze"


class ApplianceEntity:
    entity_type: int | None = None

    def __init__(
        self,
        name,
        attr,
        device_class=None,
        entity_category: EntityCategory = UNDEFINED,
        state_class: SensorStateClass | str | None = None,
    ) -> None:
        self.attr = attr
        # The state attribute the entity reads; attr stays the unique
        # identity even when several entities share one source attribute.
        self.source_attr = attr
        self.name = name
        self.device_class = device_class
        self.entity_category = entity_category
        self.state_class = state_class
        self._state = None

    def setup(self, data):
        self._state = data[self.source_attr]
        return self

    def clear_state(self):
        self._state = None

    @property
    def state(self):
        return self._state


class ApplianceSensor(ApplianceEntity):
    entity_type: int = Platform.SENSOR

    def __init__(
        self,
        name,
        attr,
        unit="",
        device_class=None,
        entity_category: EntityCategory = UNDEFINED,
        state_class: SensorStateClass | str | None = None,
    ) -> None:
        super().__init__(name, attr, device_class, entity_category, state_class)
        self.unit = unit


class ApplianceFan(ApplianceEntity):
    entity_type: int = Platform.FAN

    def __init__(self, name, attr) -> None:
        super().__init__(name, attr)


class ApplianceVacuum(ApplianceEntity):
    entity_type: int = Platform.VACUUM

    def __init__(self, name, attr) -> None:
        super().__init__(name, attr)


class ApplianceBinary(ApplianceEntity):
    entity_type: int = Platform.BINARY_SENSOR

    def __init__(
        self, name, attr, device_class=None, entity_category: EntityCategory = UNDEFINED
    ) -> None:
        super().__init__(name, attr, device_class, entity_category)

    @property
    def state(self):
        if isinstance(self._state, str):
            return self._state.casefold() in {
                "active",
                "connected",
                "enabled",
                "on",
                "running",
                "true",
                "yes",
            }
        return self._state is True or self._state == 1


class ApplianceClimate(ApplianceEntity):
    entity_type: int = Platform.CLIMATE

    def __init__(self, name, attr) -> None:
        super().__init__(name, attr)


class ApplianceHumidifier(ApplianceEntity):
    entity_type: int = Platform.HUMIDIFIER

    def __init__(self, name, attr) -> None:
        super().__init__(name, attr)


class ApplianceSelect(ApplianceEntity):
    entity_type: int = Platform.SELECT

    def __init__(
        self,
        name,
        attr,
        options: list[str] | None = None,
        entity_category: EntityCategory = UNDEFINED,
    ) -> None:
        super().__init__(name, attr, None, entity_category)
        self.options = options or []


class ApplianceErrorBinary(ApplianceBinary):
    """Aggregated problem sensor: on while any of the appliance's error flags is active."""

    def __init__(self, name, attr, error_attrs: list[str]) -> None:
        super().__init__(
            name, attr, BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC
        )
        self.error_attrs = error_attrs
        # The entity is created whenever the first error flag is reported.
        self.source_attr = error_attrs[0]
        self.active_errors: list[str] = []

    def setup(self, data):
        self.active_errors = [
            error
            for error in self.error_attrs
            if str(data.get(error, "")).casefold() == "active"
        ]
        self._state = bool(self.active_errors)
        return self


class ApplianceConsumableSensor(ApplianceSensor):
    """Remaining life of a consumable, in percent.

    The API reports usage in square metres since the consumable was last
    reset; the rated lifetimes are not exposed, so they are hard coded per
    model (reverse engineered from the percentages shown in the Electrolux
    app for a PUREi9.2).
    """

    def __init__(self, name, attr, rated_sqm) -> None:
        super().__init__(
            name,
            attr,
            unit=PERCENTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        )
        self.rated_sqm = rated_sqm

    def setup(self, data):
        self._state = max(
            0, round(100 * (1 - float(data[self.source_attr]) / self.rated_sqm))
        )
        return self


class Appliance:
    serialNumber: str
    brand: str
    device: str
    firmware: str
    mode: WorkMode
    entities: list
    capabilities: dict
    model: Model
    reported_state: dict

    def __init__(self, name, pnc_id, model) -> None:
        self.model = Model(model)
        self.pnc_id = pnc_id
        self.name = name
        self.model_name: str | None = None
        # The appliance's own Workmode; `mode` may be a virtual preset
        # (Heat / Quiet / PowerOff) derived from other properties.
        self.work_mode_raw: WorkMode = WorkMode.UNDEFINED
        self.capabilities = {}

    @property
    def display_name(self) -> str:
        """Name used for the Home Assistant device and entity ids.

        Appliance names without Latin letters or digits (e.g. the default
        Chinese "空氣清淨機") would be transliterated into unreadable entity
        ids, so fall back to the model name for those.
        """
        if any(char.isascii() and char.isalnum() for char in str(self.name)):
            return self.name
        return self.model_name or self.model.value

    @staticmethod
    def _create_entities(data):
        ultimate_home_700_entities = [
            ApplianceSensor(
                name="PM2.5",
                attr="pm25",
                unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM25,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="Hepa Filter",
                attr="hepaFilterState",
                device_class=SensorDeviceClass.ENUM,
            ),
            ApplianceSensor(
                name="Operative Mode",
                attr="operativeMode",
                device_class=SensorDeviceClass.ENUM,
            ),
            ApplianceSensor(
                name="Air Quality",
                attr="airQualityState",
                device_class=SensorDeviceClass.ENUM,
            ),
            ApplianceSensor(
                name="Ambient Temperature (Fahrenheit)",
                attr="ambientTemperatureF",
                unit=UnitOfTemperature.FAHRENHEIT,
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="Ambient Temperature (Celsius)",
                attr="ambientTemperatureC",
                unit=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="Humidity",
                attr="sensorHumidity",
                unit=PERCENTAGE,
                device_class=SensorDeviceClass.HUMIDITY,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceBinary(
                name="Connection State",
                attr="connectivityState",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            ApplianceBinary(name="Clean Air", attr="cleanAirMode"),
            ApplianceBinary(name="Vertical Swing", attr="verticalSwing"),
            ApplianceBinary(name="Water Tank Full", attr="waterTankFull"),
            ApplianceBinary(name="Appliance State", attr="applianceState"),
            ApplianceBinary(
                name="UI Lock",
                attr="uiLockMode",
                device_class=BinarySensorDeviceClass.LOCK,
            ),
            ApplianceSensor(
                name="Target Humidity",
                attr="targetHumidity",
            ),
            ApplianceSensor(
                name="Fan Speed Setting",
                attr="fanSpeedSetting",
                device_class=SensorDeviceClass.ENUM,
            ),
            ApplianceSensor(
                name="Fan Speed State",
                attr="fanSpeedState",
                device_class=SensorDeviceClass.ENUM,
            ),
        ]

        pure500_entities = [
            ApplianceSensor(
                name="PM2.5",
                attr="PM2_5_approximate",
                unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM25,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceBinary(
                name="UV State",
                attr="UVState",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ]

        pm700_entities = [
            ApplianceBinary(
                name="AQI Light",
                attr="AQILight",
                device_class=BinarySensorDeviceClass.LIGHT,
            ),
            ApplianceBinary(
                name="Humidification",
                attr="Humidification",
                device_class=BinarySensorDeviceClass.RUNNING,
            ),
            ApplianceSensor(
                name="Humidification Target",
                attr="HumidityTarget",
                unit=PERCENTAGE,
            ),
            ApplianceSensor(
                name="Louver Swing",
                attr="LouverSwing",
                device_class=SensorDeviceClass.ENUM,
            ),
            ApplianceBinary(
                name="Empty Water Tray",
                attr="WaterTrayLevelLow",
                device_class=BinarySensorDeviceClass.PROBLEM,
            ),
        ]

        a7_entities = [
            ApplianceSensor(
                name="State",
                attr="State",
                device_class=SensorDeviceClass.ENUM,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            ApplianceBinary(
                name="PM Sensor State",
                attr="PMSensState",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ]

        a9_entities = [
            ApplianceSensor(
                name=f"{FILTER_TYPE.get(data.get('FilterType', 0), 'Unknown filter')} Life",
                attr="FilterLife",
                unit=PERCENTAGE,
            ),
            ApplianceSensor(
                name="CO2",
                attr="CO2",
                unit=UnitOfRatio.PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT,
            ),
        ]

        vacuum_common = [
            ApplianceSensor(
                name="Battery",
                attr="batteryStatus",
                device_class=SensorDeviceClass.BATTERY,
                unit=PERCENTAGE,
            ),
        ]

        vacuum_purei9_entities = [
            ApplianceVacuum(
                name=data.get("applianceName", "Vacuum"),
                attr="robotStatus",
            ),
            ApplianceSensor(
                name="Dustbin Status",
                attr="dustbinStatus",
                device_class=SensorDeviceClass.ENUM,
            ),
            ApplianceSensor(
                name="Robot Status",
                attr="robotStatus",
                device_class=SensorDeviceClass.ENUM,
            ),
            ApplianceConsumableSensor(
                name="Main Brush",
                attr="main_brush_sqm",
                rated_sqm=3000,
            ),
            ApplianceConsumableSensor(
                name="Side Brush",
                attr="side_brush_sqm",
                rated_sqm=1000,
            ),
            ApplianceConsumableSensor(
                name="Filter",
                attr="filter_sqm",
                rated_sqm=1000,
            ),
        ]

        vacuum_700_series_entities = [
            ApplianceVacuum(name="Robot Status", attr="state"),
            ApplianceSensor(
                name="Cleaning Mode",
                attr="cleaningMode",
                device_class=SensorDeviceClass.ENUM,
            ),
            ApplianceSensor(
                name="Water Pump Rate",
                attr="waterPumpRate",
                device_class=SensorDeviceClass.ENUM,
            ),
            ApplianceSensor(
                name="Charging Status",
                attr="chargingStatus",
                device_class=SensorDeviceClass.ENUM,
            ),
            ApplianceBinary(name="Mop Installed", attr="mopInstalled"),
        ]

        vacuum_hygienic_700_entities = [
            ApplianceSensor(
                name="Vacuum Mode",
                attr="vacuumMode",
                device_class=SensorDeviceClass.ENUM,
            ),
        ]

        common_entities = [
            ApplianceSensor(
                name=f"{FILTER_TYPE.get(data.get('FilterType_1', 0), 'Unknown filter')} Life",
                attr="FilterLife_1",
                unit=PERCENTAGE,
            ),
            ApplianceSensor(
                name=f"{FILTER_TYPE.get(data.get('FilterType_2', 0), 'Unknown filter')} Life",
                attr="FilterLife_2",
                unit=PERCENTAGE,
            ),
            ApplianceFan(
                name="Fan Speed",
                attr="Fanspeed",
            ),
            ApplianceSensor(
                name="Temperature",
                attr="Temp",
                unit=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="TVOC",
                attr="TVOC",
                unit=UnitOfRatio.PARTS_PER_BILLION,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="eCO2",
                attr="ECO2",
                unit=UnitOfRatio.PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="PM1",
                attr="PM1",
                unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM1,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="PM2.5",
                attr="PM2_5",
                unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM25,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="PM10",
                attr="PM10",
                unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM10,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="Humidity",
                attr="Humidity",
                unit=PERCENTAGE,
                device_class=SensorDeviceClass.HUMIDITY,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="Mode", attr="Workmode", device_class=SensorDeviceClass.ENUM
            ),
            ApplianceSensor(
                name="Signal Strength",
                attr="SignalStrength",
                device_class=SensorDeviceClass.ENUM,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            ApplianceBinary(
                name="Ionizer",
                attr="Ionizer",
                device_class=BinarySensorDeviceClass.RUNNING,
            ),
            ApplianceBinary(
                name="UI Light",
                attr="UILight",
                device_class=BinarySensorDeviceClass.LIGHT,
            ),
            ApplianceBinary(
                name="Door Open",
                attr="DoorOpen",
                device_class=BinarySensorDeviceClass.DOOR,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            ApplianceBinary(
                name="Connection State",
                attr="connectionState",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            ApplianceBinary(
                name="Status", attr="status", entity_category=EntityCategory.DIAGNOSTIC
            ),
            ApplianceBinary(
                name="Safety Lock",
                attr="SafetyLock",
                device_class=BinarySensorDeviceClass.LOCK,
            ),
        ]

        # Fuji: air purifier with heater and humidifier. Humidification,
        # HumidityTarget, LouverSwing, AQILight and WaterTrayLevelLow are
        # shared with the Pure Multi 700 definitions above.
        fuji_error_flags = sorted(key for key in data if key.startswith("Err"))
        fuji_entities = [
            ApplianceSensor(
                name="Air Quality",
                attr="AQILevel",
                device_class=SensorDeviceClass.ENUM,
            ),
            # No temperature device class: HomeKit links the device's
            # temperature-class sensor to the air purifier accessory and
            # must pick the ambient "Temp" sensor, not the target.
            ApplianceSensor(
                name="Target Temperature",
                attr="TemperatureTarget",
                unit=UnitOfTemperature.CELSIUS,
            ),
            ApplianceSensor(
                name="PM Leading Mode",
                attr="PMLeadingMode",
                device_class=SensorDeviceClass.ENUM,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            ApplianceBinary(
                name="Heating",
                attr="Heating",
                device_class=BinarySensorDeviceClass.HEAT,
            ),
            ApplianceBinary(name="Quiet Fan", attr="QuietFan"),
            ApplianceBinary(
                name="UV Water Sterilisation",
                attr="UVWaterState",
                device_class=BinarySensorDeviceClass.RUNNING,
            ),
            ApplianceBinary(
                name="Monitoring",
                attr="Monitoring",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            ApplianceClimate(name="Heater", attr="Heating"),
            ApplianceHumidifier(name="Humidifier", attr="Humidification"),
            ApplianceSelect(
                name="Louver Swing",
                attr="LouverSwing",
                options=[mode.value for mode in LouverSwingMode],
                entity_category=EntityCategory.CONFIG,
            ),
            ApplianceSelect(
                name="PM Leading Mode",
                attr="PMLeadingMode",
                options=["PM1", "PM2.5", "PM10"],
                entity_category=EntityCategory.CONFIG,
            ),
            ApplianceSelect(
                name="AQI Light",
                attr="AQILight",
                options=["ambient", "on", "off"],
                entity_category=EntityCategory.CONFIG,
            ),
        ]
        if fuji_error_flags:
            fuji_entities.append(
                ApplianceErrorBinary(
                    name="Error", attr="ErrorActive", error_attrs=fuji_error_flags
                )
            )

        ac_entities = [
            ApplianceClimate(name="Climate", attr="mode"),
            ApplianceSensor(
                name="Target Temperature (Celsius)",
                attr="targetTemperatureC",
                unit=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceBinary(name="Sleep Mode", attr="sleepMode"),
            ApplianceBinary(name="Compressor State", attr="compressorState"),
        ]

        return (
            common_entities
            + a9_entities
            + a7_entities
            + pure500_entities
            + pm700_entities
            + vacuum_common
            + vacuum_purei9_entities
            + ultimate_home_700_entities
            + vacuum_700_series_entities
            + vacuum_hygienic_700_entities
            + ac_entities
            + fuji_entities
        )

    def get_entity(self, entity_type, entity_attr):
        return next(
            entity
            for entity in self.entities
            if entity.attr == entity_attr and entity.entity_type == entity_type
        )

    def get_entity_or_none(self, entity_type, entity_attr):
        return next(
            (
                entity
                for entity in self.entities
                if entity.attr == entity_attr and entity.entity_type == entity_type
            ),
            None,
        )

    def has_capability(self, capability) -> bool:
        capability_data = self.capabilities.get(capability)
        return (
            isinstance(capability_data, dict)
            and capability_data.get("access") == "readwrite"
        )

    def capability_range(
        self,
        capability: str,
        default_min: float,
        default_max: float,
        default_step: float,
    ) -> tuple[float, float, float]:
        """Return (min, max, step) for a numeric capability, with fallbacks."""
        capability_data = self.capabilities.get(capability)
        if not isinstance(capability_data, dict):
            return default_min, default_max, default_step
        minimum = capability_data.get("min", default_min)
        maximum = capability_data.get("max", default_max)
        step = capability_data.get("step", default_step)
        if (
            isinstance(minimum, (int, float))
            and isinstance(maximum, (int, float))
            and isinstance(step, (int, float))
            and minimum <= maximum
            and step > 0
        ):
            return minimum, maximum, step
        return default_min, default_max, default_step

    def capability_values(self, capability: str, default: list[str]) -> list[str]:
        """Return the accepted values of a capability, with fallbacks."""
        capability_data = self.capabilities.get(capability)
        if isinstance(capability_data, dict):
            values = capability_data.get("values")
            if isinstance(values, dict) and values:
                return [str(value) for value in values]
            if isinstance(values, list) and values:
                return [str(value) for value in values]
        return default

    def clear_mode(self):
        self.mode = WorkMode.UNDEFINED

    def set_mode(self, mode: WorkMode):
        self.mode = mode

    def setup(self, data, capabilities):
        self.reported_state = data
        self.capabilities = capabilities
        self.firmware = ""
        if "FrmVer_NIU" in data:
            self.firmware = data.get("FrmVer_NIU")
        if "VmNo_NIU" in data:
            self.firmware = data.get("VmNo_NIU")
        if "applianceUiSwVersion" in data:
            self.firmware = data.get("applianceUiSwVersion")
        if "firmwareVersion" in data:
            self.firmware = data.get("firmwareVersion")
        if "Workmode" in data:
            try:
                self.work_mode_raw = WorkMode(data.get("Workmode"))
            except ValueError:
                _LOGGER.debug("Unknown Workmode %s", data.get("Workmode"))
                self.work_mode_raw = WorkMode.UNDEFINED
            self.mode = self.work_mode_raw
        elif "mode" in data:
            self.mode = data.get("mode")
        appliance_state = data.get("applianceState")
        if "Workmode" in data:
            if isinstance(appliance_state, str) and appliance_state.casefold() == "off":
                # Models powered via executeCommand keep their last Workmode while off.
                self.mode = WorkMode.OFF
            elif data.get("Heating") is True and self.has_capability("Heating"):
                self.mode = WorkMode.HEAT
            elif str(
                data.get("QuietFan", "")
            ).casefold() == "on" and self.has_capability("QuietFan"):
                self.mode = WorkMode.QUITE
        if "LouverSwingWorkmode" in data:
            self.louver_swing_mode = LouverSwingMode(data.get("LouverSwing"))
        if "powerMode" in data:
            self.power_mode = data.get("powerMode")
        if "ecoMode" in data:
            self.eco_mode = data.get("ecoMode")
        if "vacuumMode" in data:
            self.vacuum_mode = data.get("vacuumMode")

        self.entities = [
            entity.setup(data)
            for entity in Appliance._create_entities(data)
            if entity.source_attr in data
        ]

    @property
    def is_manual_fan_control(self) -> bool:
        """Whether the fan speed can be set without changing the work mode."""
        return self.work_mode_raw == WorkMode.MANUAL

    @property
    def preset_modes(self) -> list[WorkMode]:
        # Derive the available modes from what the appliance actually reports
        # in its capabilities instead of a hardcoded per-model list.
        valid_modes = {mode.value.casefold(): mode for mode in WorkMode}
        workmode_values = (self.capabilities.get("Workmode") or {}).get("values") or {}
        modes = [
            valid_modes[str(value).casefold()]
            for value in workmode_values
            if str(value).casefold() in valid_modes
        ]
        if modes:
            # Virtual presets for feature toggles; HomeKit shows them as
            # switches inside the air purifier accessory.
            if self.has_capability("Heating") and WorkMode.HEAT not in modes:
                modes.append(WorkMode.HEAT)
            if self.has_capability("QuietFan") and WorkMode.QUITE not in modes:
                modes.append(WorkMode.QUITE)
            if WorkMode.OFF not in modes and not self.supports_execute_command:
                modes.append(WorkMode.OFF)
            return modes
        if self.model == Model.Muju:
            return [WorkMode.AUTO, WorkMode.QUITE, WorkMode.MANUAL, WorkMode.OFF]
        return [WorkMode.AUTO, WorkMode.MANUAL, WorkMode.OFF]

    def work_mode_from_preset_mode(self, preset_mode: str | None) -> WorkMode:
        if preset_mode:
            return WorkMode(preset_mode)
        presets = self.preset_modes
        for mode in (WorkMode.AUTO, WorkMode.SMART, WorkMode.MANUAL):
            if mode in presets:
                return mode
        return WorkMode.AUTO

    @property
    def supports_execute_command(self) -> bool:
        """Whether power is controlled with executeCommand on/off (e.g. Fuji)."""
        capability = self.capabilities.get("executeCommand")
        return isinstance(capability, dict)

    def work_mode_command_value(self, mode: WorkMode) -> str:
        """Return the Workmode value the appliance accepts for a mode.

        Some appliances (Fuji) report "Auto" but only accept "auto".
        """
        workmode_values = (self.capabilities.get("Workmode") or {}).get("values") or {}
        for value in workmode_values:
            if str(value).casefold() == mode.value.casefold():
                return str(value)
        return mode.value

    @property
    def speed_range(self) -> tuple[int, int]:
        fan_speed = self.capabilities.get("Fanspeed", {})
        minimum = fan_speed.get("min")
        maximum = fan_speed.get("max")
        if isinstance(minimum, int) and isinstance(maximum, int) and minimum <= maximum:
            # Speed 0 is "stopped"; Home Assistant models that as off.
            return max(minimum, 1), max(maximum, 1)

        ## Electrolux Devices:
        if self.model == Model.Muju:
            return 1, 3
        if self.model == Model.WELLA5:
            return 1, 5
        if self.model == Model.WELLA7:
            return 1, 5
        if self.model == Model.PUREA9:
            return 1, 9

        ## AEG Devices:
        if self.model == Model.AX5:
            return 1, 5
        if self.model == Model.AX7:
            return 1, 5
        if self.model == Model.AX9:
            return 1, 9
        if self.model == Model.PM700:
            return 1, 5

        return 0, 0

    @property
    def battery_range(self) -> tuple[int, int]:
        match Model(self.model):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                return 1, 100
            case Model.PUREi9.value:
                return (
                    2,
                    6,
                )  # Do not include lowest value of 1 to make this mean empty (0%) battery
        return 1, 100  # Default battery range

    @property
    def vacuum_fan_speed_list(self) -> list[str]:
        """Return the available fan speeds for the vacuum cleaner."""
        match Model(self.model):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                return list(FAN_SPEEDS_700SERIES.keys())
            case Model.PUREi9.value:
                if hasattr(self, "power_mode"):
                    return list(FAN_SPEEDS_PUREI92.keys())
                if hasattr(self, "eco_mode"):
                    return list(FAN_SPEEDS_PUREI9.keys())
                return ["power"]
        return []

    @property
    def vacuum_fan_speed(self) -> str | None:
        """Return the current fan speed of the vacuum cleaner."""
        match Model(self.model):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                return next(
                    (
                        speed
                        for speed, mode in FAN_SPEEDS_700SERIES.items()
                        if mode == self.vacuum_mode
                    ),
                    None,
                )
            case Model.PUREi9.value:
                if hasattr(self, "power_mode"):
                    return next(
                        (
                            speed
                            for speed, mode in FAN_SPEEDS_PUREI92.items()
                            if mode == self.power_mode
                        ),
                        None,
                    )
                if hasattr(self, "eco_mode"):
                    return next(
                        (
                            speed
                            for speed, mode in FAN_SPEEDS_PUREI9.items()
                            if mode == self.eco_mode
                        ),
                        None,
                    )
                return "power"
        return None

    def vacuum_set_fan_speed(self, speed: str) -> None:
        """Set the current fan speed of the vacuum cleaner."""
        match Model(self.model):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                self.vacuum_mode = FAN_SPEEDS_700SERIES.get(speed, self.vacuum_mode)
            case Model.PUREi9.value:
                if hasattr(self, "power_mode"):
                    self.power_mode = FAN_SPEEDS_PUREI92.get(speed, self.power_mode)
                if hasattr(self, "eco_mode"):
                    self.eco_mode = FAN_SPEEDS_PUREI9.get(speed, self.eco_mode)


def _is_writable(capabilities: dict, name: str) -> bool:
    capability = capabilities.get(name)
    return isinstance(capability, dict) and capability.get("access") == "readwrite"


def _api_capabilities(appliance: ApiAppliance) -> dict:
    """Capabilities of a pyelectroluxgroup appliance, or {} when unavailable."""
    capabilities = getattr(appliance, "capabilities_data", None)
    return capabilities if isinstance(capabilities, dict) else {}


def _api_reported(appliance: ApiAppliance) -> dict:
    """Reported state of a pyelectroluxgroup appliance, or {} when unavailable."""
    try:
        state = appliance.state
    except (KeyError, TypeError, AttributeError):
        return {}
    return state if isinstance(state, dict) else {}


class Appliances:
    def __init__(self, appliances) -> None:
        self.appliances = appliances

    def get_appliance(self, pnc_id):
        return self.appliances.get(pnc_id, None)


class WellbeingApiClient:
    def __init__(self, hub: ElectroluxHubAPI) -> None:
        """Sample API Client."""
        self._api_appliances: dict[str, ApiAppliance] = {}
        self._hub = hub
        self._load_lock = asyncio.Lock()
        self._livestream_revision = 0
        self._livestream_updates: dict[str, dict[str, tuple[int, object]]] = {}

    async def _ensure_loaded(self) -> None:
        if self._api_appliances:
            return
        async with self._load_lock:
            if self._api_appliances:
                return
            appliances: list[ApiAppliance] = await self._hub.async_get_appliances()
            self._api_appliances = {appliance.id: appliance for appliance in appliances}

    def update_appliance_state(self, ha_appliances, appliance_id, property_name, value):
        appliance = self._api_appliances.get(appliance_id)
        if appliance is None:
            return False

        self._livestream_revision += 1
        self._livestream_updates.setdefault(appliance_id, {})[property_name] = (
            self._livestream_revision,
            value,
        )
        self._set_appliance_state(appliance, property_name, value)

        _LOGGER.debug(
            f"Live stream update for {appliance_id}: {property_name} = {value}"
        )

        ha_appliance = ha_appliances.get_appliance(appliance_id)
        if ha_appliance is not None:
            data = appliance.state
            data["status"] = appliance.state_data.get("status", "unknown")
            data["connectionState"] = appliance.state_data.get(
                "connectionState", "unknown"
            )
            ha_appliance.setup(data, appliance.capabilities_data)

        return True

    @staticmethod
    def _set_appliance_state(appliance, property_name, value) -> None:
        if property_name in ["status", "connectionState"]:
            appliance.state_data[property_name] = value
        else:
            if "properties" not in appliance.state_data:
                appliance.state_data["properties"] = {}
            if "reported" not in appliance.state_data["properties"]:
                appliance.state_data["properties"]["reported"] = {}
            appliance.state_data["properties"]["reported"][property_name] = value

    def _reapply_concurrent_livestream_updates(
        self, appliance, poll_revision: int
    ) -> None:
        for property_name, (revision, value) in self._livestream_updates.get(
            appliance.id, {}
        ).items():
            if revision > poll_revision:
                self._set_appliance_state(appliance, property_name, value)

    async def async_get_appliances(self) -> Appliances:
        """Get data from the API."""

        await self._ensure_loaded()
        for appliance in self._api_appliances.values():
            poll_revision = self._livestream_revision
            await appliance.async_update()
            # The poll supersedes earlier stream values. Preserve only events
            # received while this appliance request was in flight.
            self._reapply_concurrent_livestream_updates(appliance, poll_revision)

        found_appliances = {}
        for appliance in (appliance for appliance in self._api_appliances.values()):
            model_name = appliance.type
            appliance_id = appliance.id
            appliance_name = appliance.name

            _LOGGER.debug(f"Appliance initial: {appliance.initial_data}")
            _LOGGER.debug(f"Appliance state: {appliance.state}")

            if (
                appliance.device_type != "AIR_PURIFIER"
                and appliance.device_type != "ROBOTIC_VACUUM_CLEANER"
                and appliance.device_type != "MULTI_AIR_PURIFIER"
                and appliance.device_type != "DEHUMIDIFIER"
                and appliance.device_type != "PORTABLE_AIR_CONDITIONER"
                and model_name not in {model.value for model in Model}
            ):
                continue

            try:
                app = Appliance(appliance_name, appliance_id, model_name)
            except ValueError:
                _LOGGER.warning(
                    "Skipping unsupported %s appliance %s with model %s",
                    appliance.device_type,
                    appliance_id,
                    model_name,
                )
                continue
            app.brand = appliance.brand
            app.serialNumber = appliance.serial_number
            app.device = appliance.device_type
            try:
                model_name = appliance.model
            except (AttributeError, KeyError, TypeError):
                model_name = None
            app.model_name = model_name if isinstance(model_name, str) else None

            data = appliance.state
            data["status"] = appliance.state_data.get("status", "unknown")
            data["connectionState"] = appliance.state_data.get(
                "connectionState", "unknown"
            )

            app.setup(data, appliance.capabilities_data)

            found_appliances[app.pnc_id] = app

        return Appliances(found_appliances)

    async def vacuum_start(self, pnc_id: str):
        """Start a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to send vacuum start command for appliance with id {pnc_id}"
            )
            return
        data = {}
        match Model(appliance.type):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                data = {"cleaningCommand": "startGlobalClean"}
            case Model.PUREi9.value:
                data = {"CleaningCommand": "play"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum start command: {result}")

    async def vacuum_stop(self, pnc_id: str):
        """Stop a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to send vacuum stop command for appliance with id {pnc_id}"
            )
            return
        data = {}
        match Model(appliance.type):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                data = {"cleaningCommand": "stopClean"}
            case Model.PUREi9.value:
                data = {"CleaningCommand": "stop"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum stop command: {result}")

    async def vacuum_pause(self, pnc_id: str):
        """Pause a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to send vacuum pause command for appliance with id {pnc_id}"
            )
            return
        data = {}
        match Model(appliance.type):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                data = {"cleaningCommand": "pauseClean"}
            case Model.PUREi9.value:
                data = {"CleaningCommand": "pause"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum pause command: {result}")

    async def vacuum_return_to_base(self, pnc_id: str):
        """Return a vacuum cleaner to its base."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to send vacuum return to base command for appliance with id {pnc_id}"
            )
            return
        data = {}
        match Model(appliance.type):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                data = {"cleaningCommand": "startGoToCharger"}
            case Model.PUREi9.value:
                data = {"CleaningCommand": "home"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum return to base command: {result}")

    async def vacuum_set_fan_speed(self, pnc_id: str, appliance, speed: str):
        """Set the fan speed of a vacuum cleaner."""
        api_appliance = self._api_appliances.get(pnc_id, None)
        if api_appliance is None:
            _LOGGER.error(f"Failed to set fan speed for appliance with id {pnc_id}")
            return
        data = dict[str, str | int | None]()
        match Model(api_appliance.type):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                data = {"vacuumMode": FAN_SPEEDS_700SERIES.get(speed)}
            case Model.PUREi9.value:
                if hasattr(appliance, "power_mode"):
                    data = {"powerMode": FAN_SPEEDS_PUREI92.get(speed)}
                if hasattr(appliance, "eco_mode"):
                    data = {"ecoMode": FAN_SPEEDS_PUREI9.get(speed)}
        result = await api_appliance.send_command(data)
        _LOGGER.debug(f"Set Fan Speed command: {result}")
        appliance.vacuum_set_fan_speed(speed)

    async def vacuum_get_segments(self, pnc_id: str) -> list[Segment]:
        """Get the segments (zones or rooms) of a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to get segments for appliance with id {pnc_id}")
            return []

        if (
            appliance.type == Model.Robot700series.value
            or appliance.type == Model.VacuumHygienic700.value
            or appliance.type == Model.Cybele.value
        ):
            api_maps = await appliance.async_get_memory_maps()
            api_map = api_maps[0] if api_maps else None  # Default to the first map
            if not api_map:
                _LOGGER.error(f"No memory maps found for appliance with id {pnc_id}")
                return []
            return [Segment(id=room.id, name=room.name) for room in api_map.rooms]

        if appliance.type == Model.PUREi9.value:
            api_maps = await appliance.async_get_interactive_maps()
            api_map = api_maps[0] if api_maps else None  # Default to the first map
            if not api_map:
                _LOGGER.error(
                    f"No interactive maps found for appliance with id {pnc_id}"
                )
                return []
            return [
                Segment(id=zone.id, name=zone.name)
                for zone in api_map.zones
                if zone.type == "clean"
            ]

        return []

    async def vacuum_clean_segments(self, pnc_id: str, segment_ids: list[str]) -> None:
        """Clean the segments (zones or rooms) of a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to clean segments for appliance with id {pnc_id}")
            return

        if (
            appliance.type == Model.Robot700series.value
            or appliance.type == Model.VacuumHygienic700.value
            or appliance.type == Model.Cybele.value
        ):
            api_maps = await appliance.async_get_memory_maps()
            api_map = api_maps[0] if api_maps else None
            if not api_map:
                _LOGGER.error(f"No memory maps found for appliance with id {pnc_id}")
                return
            if appliance.type == Model.Cybele.value:
                command_payload = {
                    "mapCommand": "selectRoomsClean",
                    "mapId": api_map.id,
                    "type": 0,
                    "roomInfo": [{"roomId": segment_id} for segment_id in segment_ids],
                }
            else:
                command_payload = {
                    "mapCommand": "selectRoomsClean",
                    "mapId": api_map.id,
                    "type": 1,
                    "roomInfo": [
                        {
                            "roomId": segment_id,
                            "sweepMode": 0,
                            "vacuumMode": "standard",
                            "waterPumpRate": "off",
                            "numberOfCleaningRepetitions": 1,
                        }
                        for segment_id in segment_ids
                    ],
                }
            result = await appliance.send_command(command_payload)
            _LOGGER.debug(
                f"Sent clean segments command with data: {command_payload}, result: {result}"
            )
            return

        if appliance.type == Model.PUREi9.value:
            api_maps = await appliance.async_get_interactive_maps()
            api_map = api_maps[0] if api_maps else None  # Default to the first map
            if not api_map:
                _LOGGER.error(
                    f"No interactive maps found for appliance with id {pnc_id}"
                )
                return
            zone_power_mode = {zone.id: zone.power_mode for zone in api_map.zones}
            default_power_mode = FAN_SPEEDS_PUREI92.get("smart", 2)
            zones_payload = [
                {
                    "zoneId": segment_id,
                    "powerMode": zone_power_mode.get(segment_id, default_power_mode),
                }
                for segment_id in segment_ids
            ]
            command_payload = {
                "CustomPlay": {"persistentMapId": api_map.id, "zones": zones_payload}
            }
            result = await appliance.send_command(command_payload)
            _LOGGER.debug(
                f"Sent clean segments command with data: {command_payload}, result: {result}"
            )
            return

    async def vacuum_send_command(
        self, pnc_id: str, command: str, params: dict | None = None
    ):
        """Send a command to the vacuum cleaner. Currently not used for any specific command."""

        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to send command '{command}' for appliance with id {pnc_id}"
            )
            return

        if command == "clean_room" and appliance.type == Model.VacuumHygienic700.value:
            if params is None:
                raise ServiceValidationError(
                    f"Parameters are required for command '{command}'"
                )
            api_maps = await appliance.async_get_memory_maps()

            # Get mapid
            api_map = next(
                (x for x in api_maps if x.data.get("name") == params["map_name"]), None
            )
            if not api_map:
                raise ServiceValidationError(f"{params['map_name']} does not exist")

            # validate input and convert it to expected format
            room_playload = {
                "mapCommand": "selectRoomsClean",
                "mapId": api_map.id,
                "type": 1,
            }
            room_info = []
            for room in params["room_info"]:
                room_id = next(
                    (
                        r["id"]
                        for r in api_map.data.get("rooms", [])
                        if r["name"] == room["room_name"]
                    ),
                    None,
                )
                if room_id is None:
                    raise ServiceValidationError(f"{room['room_name']} does not exist")

                sweep_mode = room["sweep_mode"]
                if sweep_mode not in [0, 1]:
                    sweep_mode = 0
                    _LOGGER.debug("Invalid sweep_mode input 0 (only sweep) applied.")

                vacuum_mode = FAN_SPEEDS_700SERIES.get(room["vacuum_mode"])
                if not isinstance(vacuum_mode, str):
                    vacuum_mode = "standard"
                    _LOGGER.debug(
                        f"Vacuum mode for {room['room_name']} does not exist, standard mode used."
                    )

                water_pump_rate = room["water_pump_rate"]
                if water_pump_rate not in WATER_PUMP_RATES_700SERIES:
                    water_pump_rate = "off"
                    _LOGGER.debug("Invalid water_pump_rate, 'off' applied.")

                repetitions = room["repetitions"]
                if not isinstance(repetitions, int):
                    repetitions = 1
                    _LOGGER.debug(
                        f"Repetition 1 used as {room['room_name']} input is invalid."
                    )

                room_info.append(
                    {
                        "roomId": room_id,
                        "sweepMode": sweep_mode,
                        "vacuumMode": vacuum_mode,
                        "waterPumpRate": water_pump_rate,
                        "numberOfCleaningRepetitions": repetitions,
                    }
                )
            room_playload["roomInfo"] = room_info

            # send command
            result = await appliance.send_command(room_playload)
            _LOGGER.debug(
                f"Sent command '{command}' with data: {room_playload}, result: {result}"
            )
            return

        if command == "clean_zones" and appliance.type == Model.PUREi9.value:
            # Validate and process the parameters for the PUREi9 interactive map command.
            try:
                params = INTERACTIVE_MAP_SCHEMA(params)
            except vol.Invalid as e:
                raise ServiceValidationError(
                    f"Invalid parameters for command '{command}': {e}"
                ) from e
            assert isinstance(params, dict)  # Needed for mypy type checking
            # Build the command payload for the PUREi9 interactive map.
            api_maps = await appliance.async_get_interactive_maps()
            api_map = next((m for m in api_maps if m.name == params["map"]), None)
            if not api_map:
                raise ServiceValidationError(
                    f"Map '{params['map']}' not found for appliance with id {pnc_id}"
                )
            zones_payload = []
            for zone in params["zones"]:
                api_zone = next(
                    (z for z in api_map.zones if z.name == zone["zone"]), None
                )
                if not api_zone:
                    raise ServiceValidationError(
                        f"Zone '{zone['zone']}' not found in map '{params['map']}'"
                    )
                zones_payload.append(
                    {
                        "zoneId": api_zone.id,
                        "powerMode": FAN_SPEEDS_PUREI92.get(
                            zone.get("fan_speed"), api_zone.power_mode
                        ),
                    }
                )
            command_payload = {
                "CustomPlay": {"persistentMapId": api_map.id, "zones": zones_payload}
            }
            # Send the command to the appliance.
            result = await appliance.send_command(command_payload)
            _LOGGER.debug(
                f"Sent command '{command}' with data: {command_payload}, result: {result}"
            )
            return

        raise ServiceValidationError(
            f"Command '{command}' is not recognized for appliance with id {pnc_id}"
        )

    async def set_fan_speed(self, pnc_id: str, level: int):
        data = {"Fanspeed": level}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set fan speed for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set Fan Speed: {result}")

    async def set_work_mode(
        self, pnc_id: str, mode: WorkMode, ha_appliance: Appliance | None = None
    ):
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set work mode for appliance with id {pnc_id}")
            return

        capabilities = _api_capabilities(appliance)
        uses_execute_command = isinstance(capabilities.get("executeCommand"), dict)
        workmode_values = (capabilities.get("Workmode") or {}).get("values") or {}
        accepted = {str(value).casefold(): str(value) for value in workmode_values}

        if mode == WorkMode.OFF and uses_execute_command and "poweroff" not in accepted:
            result = await appliance.send_command({"executeCommand": "off"})
            _LOGGER.debug(f"Power off: {result}")
            return

        reported = _api_reported(appliance)
        if uses_execute_command and mode != WorkMode.OFF:
            appliance_state = reported.get("applianceState")
            if isinstance(appliance_state, str) and appliance_state.casefold() == "off":
                result = await appliance.send_command({"executeCommand": "on"})
                _LOGGER.debug(f"Power on: {result}")

        heating_writable = _is_writable(capabilities, "Heating")
        quiet_writable = _is_writable(capabilities, "QuietFan")
        if mode == WorkMode.HEAT and heating_writable:
            result = await appliance.send_command({"Heating": True})
            _LOGGER.debug(f"Set heating on: {result}")
            return
        if mode == WorkMode.QUITE and quiet_writable:
            # QuietFan is only accepted while the appliance is in Auto.
            if str(reported.get("Workmode", "")).casefold() != "auto":
                value = accepted.get("auto", WorkMode.AUTO.value)
                result = await appliance.send_command({"Workmode": value})
                _LOGGER.debug(f"Set work mode: {result}")
            result = await appliance.send_command({"QuietFan": "on"})
            _LOGGER.debug(f"Set quiet fan on: {result}")
            return

        # Leaving a virtual preset: clear the feature it stands for first.
        if quiet_writable and str(reported.get("QuietFan", "")).casefold() == "on":
            result = await appliance.send_command({"QuietFan": "off"})
            _LOGGER.debug(f"Set quiet fan off: {result}")
        if heating_writable and reported.get("Heating") is True:
            result = await appliance.send_command({"Heating": False})
            _LOGGER.debug(f"Set heating off: {result}")

        value = accepted.get(mode.value.casefold(), mode.value)
        result = await appliance.send_command({"Workmode": value})
        _LOGGER.debug(f"Set work mode: {result}")

    async def set_feature_state(self, pnc_id: str, feature: str, state: bool):
        """Set the state of a feature (Ionizer, UILight, SafetyLock, ...).

        Boolean features take true/false; features reported as a string
        (e.g. UVWaterState, QuietFan on the Fuji) take "on"/"off".
        """
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to set feature {feature} for appliance with id {pnc_id}"
            )
            return

        reported = _api_reported(appliance).get(feature)
        value: bool | str = state
        if isinstance(reported, str) and reported.casefold() in {"on", "off"}:
            value = "on" if state else "off"
        data = {feature: value}

        await appliance.send_command(data)
        _LOGGER.debug(f"Set {feature} State to {value}")

    async def set_property(self, pnc_id: str, name: str, value):
        """Send a single property command (e.g. TemperatureTarget, LouverSwing)."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set {name} for appliance with id {pnc_id}")
            return

        result = await appliance.send_command({name: value})
        _LOGGER.debug(f"Set {name} to {value}: {result}")

    async def ac_set_temperature(self, pnc_id: str, temp: float):
        data = {"targetTemperatureC": temp}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to set AC temperature for appliance with id {pnc_id}"
            )
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set AC temperature: {result}")

    async def ac_set_mode(self, pnc_id: str, mode: str):
        data = {"mode": mode.upper()}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set AC mode for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set AC mode: {result}")

    async def ac_set_fan_mode(self, pnc_id: str, fan_mode: str):
        data = {"fanSpeedSetting": fan_mode}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set AC fan mode for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set AC fan mode: {result}")

    async def ac_set_vertical_swing(self, pnc_id: str, state: str):
        data = {"verticalSwing": state.upper()}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to set AC vertical swing for appliance with id {pnc_id}"
            )
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set AC vertical swing: {result}")

    async def ac_set_sleep_mode(self, pnc_id: str, state: str):
        data = {"sleepMode": state.upper()}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set AC sleep mode for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set AC sleep mode: {result}")

    async def ac_turn_on(self, pnc_id: str):
        data = {"executeCommand": "ON"}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to turn on AC for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Turn on AC: {result}")

    async def ac_turn_off(self, pnc_id: str):
        data = {"executeCommand": "OFF"}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to turn off AC for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Turn off AC: {result}")
