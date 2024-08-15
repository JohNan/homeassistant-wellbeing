"""Sample API Client."""
import logging
from enum import Enum

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, PERCENTAGE, CONCENTRATION_PARTS_PER_MILLION, \
    CONCENTRATION_PARTS_PER_BILLION, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, Platform, EntityCategory
from homeassistant.helpers.typing import UNDEFINED
from pyelectroluxgroup.api import ElectroluxHubAPI
from pyelectroluxgroup.appliance import Appliance as ApiAppliance

FILTER_TYPE = {
    48: "BREEZE Complete air filter",
    49: "CLEAN Ultrafine particle filter",
    51: "CARE Ultimate protect filter",
    64: "Breeze 360 filter",
    65: "Clean 360 Ultrafine particle filter",
    66: "Protect 360 filter",
    67: "Breathe 360 filter",
    68: "Fresh 360 filter",
    96: "Breeze 360 filter",
    99: "Breeze 360 filter",
    100: "Fresh 360 filter",
    192: "FRESH Odour protect filter",
    0: "Filter"
}

_LOGGER: logging.Logger = logging.getLogger(__package__)


class Mode(str, Enum):
    OFF = "PowerOff"
    AUTO = "Auto"
    MANUAL = "Manual"
    UNDEFINED = "Undefined"


class ApplianceEntity:
    entity_type: int = None

    def __init__(
            self,
            name,
            attr,
            device_class=None,
            entity_category: EntityCategory = UNDEFINED,
            state_class: SensorStateClass | str | None = None
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
            state_class: SensorStateClass | str | None = None
    ) -> None:
        super().__init__(name, attr, device_class, entity_category, state_class)
        self.unit = unit


class ApplianceFan(ApplianceEntity):
    entity_type: int = Platform.FAN

    def __init__(self, name, attr) -> None:
        super().__init__(name, attr)


class ApplianceBinary(ApplianceEntity):
    entity_type: int = Platform.BINARY_SENSOR

    def __init__(self, name, attr, device_class=None, entity_category: EntityCategory = UNDEFINED) -> None:
        super().__init__(name, attr, device_class, entity_category)

    @property
    def state(self):
        return self._state in ['enabled', True, 'Connected', 'on']


class Appliance:
    serialNumber: str
    brand: str
    device: str
    firmware: str
    mode: Mode
    entities: []
    capabilities: {}

    def __init__(self, name, pnc_id, model) -> None:
        self.model = model
        self.pnc_id = pnc_id
        self.name = name

    @staticmethod
    def _create_entities(data):
        pure500_entities = [
            ApplianceSensor(
                name="PM2.5",
                attr='PM2_5_approximate',
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM25,
                state_class=SensorStateClass.MEASUREMENT
            ),
            ApplianceBinary(
                name='UV State',
                attr='UVState',
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]

        a7_entities = [
            ApplianceSensor(
                name=f"{FILTER_TYPE.get(data.get('FilterType_1', 0), 'Unknown filter')} Life",
                attr='FilterLife_1',
                unit=PERCENTAGE
            ),
            ApplianceSensor(
                name=f"{FILTER_TYPE.get(data.get('FilterType_2', 0), 'Unknown filter')} Life",
                attr='FilterLife_2',
                unit=PERCENTAGE
            ),
            ApplianceSensor(
                name='State',
                attr='State',
                entity_category=EntityCategory.DIAGNOSTIC
            ),
            ApplianceBinary(
                name='PM Sensor State',
                attr='PMSensState',
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]

        a9_entities = [
            ApplianceSensor(
                name=f"{FILTER_TYPE.get(data.get('FilterType', 0), 'Unknown filter')} Life",
                attr='FilterLife',
                unit=PERCENTAGE
            ),
            ApplianceSensor(
                name="CO2",
                attr='CO2',
                unit=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT
            )
        ]

        common_entities = [
            ApplianceFan(
                name="Fan Speed",
                attr='Fanspeed',
            ),
            ApplianceSensor(
                name="Temperature",
                attr='Temp',
                unit=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT
            ),
            ApplianceSensor(
                name="TVOC",
                attr='TVOC',
                unit=CONCENTRATION_PARTS_PER_BILLION,
                state_class=SensorStateClass.MEASUREMENT
            ),
            ApplianceSensor(
                name="eCO2",
                attr='ECO2',
                unit=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT
            ),
            ApplianceSensor(
                name="PM1",
                attr='PM1',
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM1,
                state_class=SensorStateClass.MEASUREMENT
            ),
            ApplianceSensor(
                name="PM2.5",
                attr='PM2_5',
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM25,
                state_class=SensorStateClass.MEASUREMENT
            ),
            ApplianceSensor(
                name="PM10",
                attr='PM10',
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM10,
                state_class=SensorStateClass.MEASUREMENT
            ),
            ApplianceSensor(
                name="Humidity",
                attr='Humidity',
                unit=PERCENTAGE,
                device_class=SensorDeviceClass.HUMIDITY,
                state_class=SensorStateClass.MEASUREMENT
            ),
            ApplianceSensor(
                name="Mode",
                attr='Workmode',
                device_class=SensorDeviceClass.ENUM
            ),
            ApplianceSensor(
                name="Signal Strength",
                attr='SignalStrength',
                device_class=SensorDeviceClass.ENUM,
                entity_category=EntityCategory.DIAGNOSTIC
            ),
            ApplianceBinary(
                name="Ionizer",
                attr='Ionizer'
            ),
            ApplianceBinary(
                name="UI Light",
                attr='UILight'
            ),
            ApplianceBinary(
                name="Door Open",
                attr='DoorOpen',
                device_class=BinarySensorDeviceClass.DOOR,
                entity_category=EntityCategory.DIAGNOSTIC
            ),
            ApplianceBinary(
                name="Connection State",
                attr='connectionState',
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                entity_category=EntityCategory.DIAGNOSTIC
            ),
            ApplianceBinary(
                name="Status",
                attr='status',
                entity_category=EntityCategory.DIAGNOSTIC
            ),
            ApplianceBinary(
                name="Safety Lock",
                attr='SafetyLock',
                device_class=BinarySensorDeviceClass.LOCK
            )
        ]

        return common_entities + a9_entities + a7_entities + pure500_entities

    def get_entity(self, entity_type, entity_attr):
        return next(
            entity
            for entity in self.entities
            if entity.attr == entity_attr and entity.entity_type == entity_type
        )

    def has_capability(self, capability) -> bool:
        return capability in self.capabilities and self.capabilities[capability]['access'] == 'readwrite'

    def clear_mode(self):
        self.mode = Mode.UNDEFINED

    def setup(self, data, capabilities):
        self.firmware = data.get('FrmVer_NIU')
        self.mode = Mode(data.get('Workmode'))
        self.capabilities = capabilities
        self.entities = [
            entity.setup(data)
            for entity in Appliance._create_entities(data) if entity.attr in data
        ]

    @property
    def speed_range(self) -> tuple[int, int]:
        ## Electrolux Devices:
        if self.model == "Muju":
            return 1, 3
        if self.model == "WELLA5":
            return 1, 5
        if self.model == "WELLA7":
            return 1, 5
        if self.model == "PUREA9":
            return 1, 9

        ## AEG Devices:
        if self.model == "AX5":
            return 1, 5
        if self.model == "AX7":
            return 1, 5
        if self.model == "AX9":
            return 1, 9

        return 0, 0


class Appliances:
    def __init__(self, appliances) -> None:
        self.appliances = appliances

    def get_appliance(self, pnc_id):
        return self.appliances.get(pnc_id, None)


class WellbeingApiClient:

    def __init__(self, hub: ElectroluxHubAPI) -> None:
        """Sample API Client."""
        self._api_appliances: {str: ApiAppliance} = None
        self._hub = hub

    async def async_get_appliances(self) -> Appliances:
        """Get data from the API."""

        appliances: [ApiAppliance] = await self._hub.async_get_appliances()
        self._api_appliances = dict((appliance.id, appliance) for appliance in appliances)

        found_appliances = {}
        for appliance in (appliance for appliance in appliances):
            await appliance.async_update()

            model_name = appliance.type
            appliance_id = appliance.id
            appliance_name = appliance.name

            app = Appliance(appliance_name, appliance_id, model_name)
            _LOGGER.debug(f"Appliance initial: {appliance.initial_data}")
            _LOGGER.debug(f"Appliance state: {appliance.state}")

            app.brand = appliance.brand
            app.serialNumber = appliance.serial_number
            app.device = appliance.device_type

            if app.device != 'AIR_PURIFIER':
                continue

            data = appliance.state
            data['status'] = appliance.state_data.get('status', 'unknown')
            data['connectionState'] = appliance.state_data.get('connectionState', 'unknown')
            app.setup(data, appliance.capabilities_data)

            found_appliances[app.pnc_id] = app

        return Appliances(found_appliances)

    async def set_fan_speed(self, pnc_id: str, level: int):
        data = {
            "Fanspeed": level
        }
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set fan speed for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set Fan Speed: {result}")

    async def set_work_mode(self, pnc_id: str, mode: Mode):
        data = {
            "Workmode": mode.value
        }
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
