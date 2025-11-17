"""Sample API Client."""

import asyncio
import logging
from enum import Enum

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.exceptions import ServiceValidationError
from homeassistant.const import (
    UnitOfTemperature,
    PERCENTAGE,
    CONCENTRATION_PARTS_PER_MILLION,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    Platform,
    EntityCategory,
)
from homeassistant.helpers.typing import UNDEFINED
from pyelectroluxgroup.api import ElectroluxHubAPI
from pyelectroluxgroup.appliance import Appliance as ApiAppliance
import voluptuous as vol

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

_LOGGER: logging.Logger = logging.getLogger(__package__)


class Model(str, Enum):
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


class WorkMode(str, Enum):
    OFF = "PowerOff"
    MANUAL = "Manual"
    UNDEFINED = "Undefined"
    SMART = "Smart"
    QUITE = "Quiet"
    AUTO = "Auto"


class LouverSwingMode(str, Enum):
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
        self.name = name
        self.device_class = device_class
        self.entity_category = entity_category
        self.state_class = state_class
        self._state = None

    def setup(self, data):
        self._state = data[self.attr]
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

    def __init__(self, name, attr, device_class=None, entity_category: EntityCategory = UNDEFINED) -> None:
        super().__init__(name, attr, device_class, entity_category)

    @property
    def state(self):
        return self._state in ["enabled", True, "Connected", "on"]


class Appliance:
    serialNumber: str
    brand: str
    device: str
    firmware: str
    mode: WorkMode
    entities: list
    capabilities: dict
    model: Model

    def __init__(self, name, pnc_id, model) -> None:
        self.model = Model(model)
        self.pnc_id = pnc_id
        self.name = name

    @staticmethod
    def _create_entities(data):
        ultimate_home_700_entities = [
            ApplianceSensor(
                name="PM2.5",
                attr="pm25",
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM25,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(name="Hepa Filter", attr="hepaFilterState", device_class=SensorDeviceClass.ENUM),
            ApplianceSensor(name="Operative Mode", attr="operativeMode", device_class=SensorDeviceClass.ENUM),
            ApplianceSensor(name="Air Quality", attr="airQualityState", device_class=SensorDeviceClass.ENUM),
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
            ApplianceBinary(name="UI Lock", attr="uiLockMode", device_class=BinarySensorDeviceClass.LOCK),
            ApplianceSensor(
                name="Target Humidity",
                attr="targetHumidity",
            ),
            ApplianceSensor(name="Fan Speed Setting", attr="fanSpeedSetting", device_class=SensorDeviceClass.ENUM),
            ApplianceSensor(name="Fan Speed State", attr="fanSpeedState", device_class=SensorDeviceClass.ENUM),
        ]

        pure500_entities = [
            ApplianceSensor(
                name="PM2.5",
                attr="PM2_5_approximate",
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
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
            ApplianceSensor(name="Louver Swing", attr="LouverSwing", device_class=SensorDeviceClass.ENUM),
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
                unit=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT,
            ),
        ]

        purei9_entities = [
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
                name="TVOC", attr="TVOC", unit=CONCENTRATION_PARTS_PER_BILLION, state_class=SensorStateClass.MEASUREMENT
            ),
            ApplianceSensor(
                name="eCO2",
                attr="ECO2",
                unit=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="PM1",
                attr="PM1",
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM1,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="PM2.5",
                attr="PM2_5",
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM25,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="PM10",
                attr="PM10",
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
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
            ApplianceSensor(name="Mode", attr="Workmode", device_class=SensorDeviceClass.ENUM),
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
            ApplianceBinary(name="Status", attr="status", entity_category=EntityCategory.DIAGNOSTIC),
            ApplianceBinary(name="Safety Lock", attr="SafetyLock", device_class=BinarySensorDeviceClass.LOCK),
        ]

        return (
            common_entities
            + a9_entities
            + a7_entities
            + pure500_entities
            + pm700_entities
            + purei9_entities
            + ultimate_home_700_entities
            + vacuum_700_series_entities
            + vacuum_hygienic_700_entities
        )

    def get_entity(self, entity_type, entity_attr):
        return next(
            entity for entity in self.entities if entity.attr == entity_attr and entity.entity_type == entity_type
        )

    def has_capability(self, capability) -> bool:
        return capability in self.capabilities and self.capabilities[capability]["access"] == "readwrite"

    def clear_mode(self):
        self.mode = WorkMode.UNDEFINED

    def set_mode(self, mode: WorkMode):
        self.mode = mode

    def setup(self, data, capabilities):
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
            self.mode = WorkMode(data.get("Workmode"))
        if "LouverSwingWorkmode" in data:
            self.louver_swing_mode = LouverSwingMode(data.get("LouverSwing"))
        if "powerMode" in data:
            self.power_mode = data.get("powerMode")
        if "ecoMode" in data:
            self.eco_mode = data.get("ecoMode")
        if "vacuumMode" in data:
            self.vacuum_mode = data.get("vacuumMode")
        if "batteryStatus" in data:
            self.battery_status = data.get("batteryStatus")

        self.capabilities = capabilities
        self.entities = [entity.setup(data) for entity in Appliance._create_entities(data) if entity.attr in data]

    @property
    def preset_modes(self) -> list[WorkMode]:
        if self.model == Model.Muju:
            return [WorkMode.SMART, WorkMode.QUITE, WorkMode.MANUAL, WorkMode.OFF]
        return [WorkMode.AUTO, WorkMode.MANUAL, WorkMode.OFF]

    def work_mode_from_preset_mode(self, preset_mode: str | None) -> WorkMode:
        if preset_mode:
            return WorkMode(preset_mode)
        if self.model == Model.Muju:
            return WorkMode.SMART
        return WorkMode.AUTO

    @property
    def speed_range(self) -> tuple[int, int]:
        ## Electrolux Devices:
        if self.model == Model.Muju:
            if self.mode is WorkMode.QUITE:
                return 1, 2
            return 1, 5
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
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                return 1, 100
            case Model.PUREi9.value:
                return 2, 6  # Do not include lowest value of 1 to make this mean empty (0%) battery
        return 0, 0

    @property
    def vacuum_fan_speed_list(self) -> list[str]:
        """Return the available fan speeds for the vacuum cleaner."""
        match Model(self.model):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
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
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                return next((speed for speed, mode in FAN_SPEEDS_700SERIES.items() if mode == self.vacuum_mode), None)
            case Model.PUREi9.value:
                if hasattr(self, "power_mode"):
                    return next((speed for speed, mode in FAN_SPEEDS_PUREI92.items() if mode == self.power_mode), None)
                if hasattr(self, "eco_mode"):
                    return next((speed for speed, mode in FAN_SPEEDS_PUREI9.items() if mode == self.eco_mode), None)
                return "power"
        return None

    def vacuum_set_fan_speed(self, speed: str) -> None:
        """Set the current fan speed of the vacuum cleaner."""
        match Model(self.model):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                self.vacuum_mode = FAN_SPEEDS_700SERIES.get(speed, self.vacuum_mode)
            case Model.PUREi9.value:
                if hasattr(self, "power_mode"):
                    self.power_mode = FAN_SPEEDS_PUREI92.get(speed, self.power_mode)
                if hasattr(self, "eco_mode"):
                    self.eco_mode = FAN_SPEEDS_PUREI9.get(speed, self.eco_mode)


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

    async def _ensure_loaded(self) -> None:
        if self._api_appliances:
            return
        async with self._load_lock:
            if self._api_appliances:
                return
            appliances: list[ApiAppliance] = await self._hub.async_get_appliances()
            self._api_appliances = {appliance.id: appliance for appliance in appliances}

    async def async_get_appliances(self) -> Appliances:
        """Get data from the API."""

        await self._ensure_loaded()
        found_appliances = {}
        for appliance in (appliance for appliance in self._api_appliances.values()):
            await appliance.async_update()

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
            ):
                continue

            app = Appliance(appliance_name, appliance_id, model_name)
            app.brand = appliance.brand
            app.serialNumber = appliance.serial_number
            app.device = appliance.device_type

            data = appliance.state
            data["status"] = appliance.state_data.get("status", "unknown")
            data["connectionState"] = appliance.state_data.get("connectionState", "unknown")

            app.setup(data, appliance.capabilities_data)

            found_appliances[app.pnc_id] = app

        return Appliances(found_appliances)

    async def vacuum_start(self, pnc_id: str):
        """Start a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to send vacuum start command for appliance with id {pnc_id}")
            return
        data = {}
        match Model(appliance.type):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                data = {"cleaningCommand": "startGlobalClean"}
            case Model.PUREi9.value:
                data = {"CleaningCommand": "play"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum start command: {result}")

    async def vacuum_stop(self, pnc_id: str):
        """Stop a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to send vacuum stop command for appliance with id {pnc_id}")
            return
        data = {}
        match Model(appliance.type):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                data = {"cleaningCommand": "stopClean"}
            case Model.PUREi9.value:
                data = {"CleaningCommand": "stop"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum stop command: {result}")

    async def vacuum_pause(self, pnc_id: str):
        """Pause a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to send vacuum pause command for appliance with id {pnc_id}")
            return
        data = {}
        match Model(appliance.type):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                data = {"cleaningCommand": "pauseClean"}
            case Model.PUREi9.value:
                data = {"CleaningCommand": "pause"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum pause command: {result}")

    async def vacuum_return_to_base(self, pnc_id: str):
        """Return a vacuum cleaner to its base."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to send vacuum return to base command for appliance with id {pnc_id}")
            return
        data = {}
        match Model(appliance.type):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
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
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                data = {"vacuumMode": FAN_SPEEDS_700SERIES.get(speed)}
            case Model.PUREi9.value:
                if hasattr(appliance, "power_mode"):
                    data = {"powerMode": FAN_SPEEDS_PUREI92.get(speed)}
                if hasattr(appliance, "eco_mode"):
                    # data = {"ecoMode": FAN_SPEEDS_PUREI9.get(speed)}
                    if speed == "eco":
                        data = {"powerMode": 1}
                    else:
                        data = {"powerMode": 3}
        result = await api_appliance.send_command(data)
        _LOGGER.debug(f"Set Fan Speed command: {result}")
        appliance.vacuum_set_fan_speed(speed)

    async def vacuum_send_command(self, pnc_id: str, command: str, params: dict | None = None):
        """Send a command to the vacuum cleaner. Currently not used for any specific command."""

        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to send command '{command}' for appliance with id {pnc_id}")
            return

        if command == "clean_zones" and appliance.type == Model.PUREi9.value:
            # Validate and process the parameters for the PUREi9 interactive map command.
            try:
                params = INTERACTIVE_MAP_SCHEMA(params)
            except vol.Invalid as e:
                raise ServiceValidationError(f"Invalid parameters for command '{command}': {e}") from e
            assert isinstance(params, dict)  # Needed for mypy type checking
            # Build the command payload for the PUREi9 interactive map.
            api_maps = await appliance.async_get_interactive_maps()
            api_map = next((m for m in api_maps if m.name == params["map"]), None)
            if not api_map:
                raise ServiceValidationError(f"Map '{params['map']}' not found for appliance with id {pnc_id}")
            zones_payload = []
            for zone in params["zones"]:
                api_zone = next((z for z in api_map.zones if z.name == zone["zone"]), None)
                if not api_zone:
                    raise ServiceValidationError(f"Zone '{zone['zone']}' not found in map '{params['map']}'")
                zones_payload.append(
                    {
                        "zoneId": api_zone.id,
                        "powerMode": FAN_SPEEDS_PUREI92.get(zone.get("fan_speed"), api_zone.power_mode),
                    }
                )
            command_payload = {"CustomPlay": {"persistentMapId": api_map.id, "zones": zones_payload}}
            # Send the command to the appliance.
            result = await appliance.send_command(command_payload)
            _LOGGER.debug(f"Sent command '{command}' with data: {command_payload}, result: {result}")
            return

        raise ServiceValidationError(f"Command '{command}' is not recognized for appliance with id {pnc_id}")

    async def set_fan_speed(self, pnc_id: str, level: int):
        data = {"Fanspeed": level}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set fan speed for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set Fan Speed: {result}")

    async def set_work_mode(self, pnc_id: str, mode: WorkMode):
        data = {"Workmode": mode.value}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set work mode for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set work mode: {result}")

    async def set_feature_state(self, pnc_id: str, feature: str, state: bool):
        """Set the state of a feature (Ionizer, UILight, SafetyLock)."""
        # Construct the command directly using the feature name
        data = {feature: state}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set feature {feature} for appliance with id {pnc_id}")
            return

        await appliance.send_command(data)
        _LOGGER.debug(f"Set {feature} State to {state}")
