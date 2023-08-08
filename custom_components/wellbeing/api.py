"""Sample API Client."""
import asyncio
import logging
import socket
import json
from datetime import datetime, timedelta
from enum import Enum

import aiohttp
import async_timeout

from custom_components.wellbeing.const import SENSOR, FAN, BINARY_SENSOR
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import TEMP_CELSIUS, PERCENTAGE, CONCENTRATION_PARTS_PER_MILLION, \
    CONCENTRATION_PARTS_PER_BILLION, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER


TIMEOUT = 10
RETRIES = 3
CLIENT_ID = "ElxOneApp"
CLIENT_SECRET = "8UKrsKD7jH9zvTV7rz5HeCLkit67Mmj68FvRVTlYygwJYy4dW6KF2cVLPKeWzUQUd6KJMtTifFf4NkDnjI7ZLdfnwcPtTSNtYvbP7OzEkmQD9IjhMOf5e1zeAQYtt2yN"
X_API_KEY = "2AMqwEV5MqVhTKrRCyYfVF8gmKrd2rAmp7cUsfky"

BASE_URL = "https://api.ocp.electrolux.one"
TOKEN_URL = f"{BASE_URL}/one-account-authorization/api/v1/token"
AUTHENTICATION_URL = f"{BASE_URL}/one-account-authentication/api/v1/authenticate"
API_URL = f"{BASE_URL}/appliance/api/v2"
APPLIANCES_URL = f"{API_URL}/appliances"

FILTER_TYPE = {
    48: "BREEZE Complete air filter",
    51: "CARE Ultimate protect filter",
    64: "Breeze 360 filter",
    96: "Breeze 360 filter",
    99: "Breeze 360 filter",
    192: "FRESH Odour protect filter",
    0: "Filter"
}

_LOGGER: logging.Logger = logging.getLogger(__package__)

HEADERS = {"Content-type": "application/json; charset=UTF-8"}

class CustomComponent:
    def get_translation(self, key):
        return translations.get(key, key)

class Mode(str, Enum):
    OFF = "PowerOff"
    AUTO = "Auto"
    MANUAL = "Manual"
    UNDEFINED = "Undefined"


class ApplianceEntity:
    entity_type: int = None

    def __init__(self, name, attr, device_class=None) -> None:
        self.attr = attr
        self.name = name
        self.device_class = device_class
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
    entity_type: int = SENSOR

    def __init__(self, name, attr, unit="", device_class=None) -> None:
        super().__init__(name, attr, device_class)
        self.unit = unit


class ApplianceFan(ApplianceEntity):
    entity_type: int = FAN

    def __init__(self, name, attr) -> None:
        super().__init__(name, attr)


class ApplianceBinary(ApplianceEntity):
    entity_type: int = BINARY_SENSOR

    def __init__(self, name, attr, device_class=None) -> None:
        super().__init__(name, attr, device_class)

    @property
    def state(self):
        return self._state in ['enabled', True, 'Connected']


class Appliance:
    serialNumber: str
    brand: str
    device: str
    firmware: str
    mode: Mode
    entities: []

    def __init__(self, name, pnc_id, model) -> None:
        self.model = model
        self.pnc_id = pnc_id
        self.name = name

    @staticmethod
    def _create_entities(data):
        a7_entities = [
            ApplianceSensor(
                name="eCO2",
                attr='ECO2',
                unit=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2
            ),
            ApplianceSensor(
                name=f"{FILTER_TYPE[data.get('FilterType_1', 0)]} Life",
                attr='FilterLife_1',
                unit=PERCENTAGE
            ),
            ApplianceSensor(
                name=f"{FILTER_TYPE[data.get('FilterType_2', 0)]} Life",
                attr='FilterLife_2',
                unit=PERCENTAGE
            ),
            ApplianceSensor(
                name='State',
                attr='State'
            ),
            ApplianceBinary(
                name='PM Sensor State',
                attr='PMSensState'
            )
        ]

        a9_entities = [
            ApplianceSensor(
                name=f"{FILTER_TYPE.get(data.get('FilterType', 0), 'Filter')} Life",
                attr='FilterLife',
                unit=PERCENTAGE
            ),
            ApplianceSensor(
                name="CO2",
                attr='CO2',
                unit=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2
            ),
        ]

        common_entities = [
            ApplianceFan(
                name="Fan Speed",
                attr='Fanspeed',
            ),
            ApplianceSensor(
                name="Temperature",
                attr='Temp',
                unit=TEMP_CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE
            ),
            ApplianceSensor(
                name="TVOC",
                attr='TVOC',
                unit=CONCENTRATION_PARTS_PER_BILLION
            ),
            ApplianceSensor(
                name="PM1",
                attr='PM1',
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM1
            ),
            ApplianceSensor(
                name="PM2.5",
                attr='PM2_5',
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM25
            ),
            ApplianceSensor(
                name="PM10",
                attr='PM10',
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM10
            ),
            ApplianceSensor(
                name="Humidity",
                attr='Humidity',
                unit=PERCENTAGE,
                device_class=SensorDeviceClass.HUMIDITY
            ),
            ApplianceSensor(
                name="Mode",
                attr='Workmode'
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
                name="Connection State",
                attr='connectionState',
                device_class=BinarySensorDeviceClass.CONNECTIVITY
            ),
            ApplianceBinary(
                name="Status",
                attr='status'
            ),
            ApplianceBinary(
                name="Safety Lock",
                attr='SafetyLock',
                device_class=BinarySensorDeviceClass.LOCK
            )
        ]

        return common_entities + a9_entities + a7_entities

    def get_entity(self, entity_type, entity_attr):
        return next(
            entity
            for entity in self.entities
            if entity.attr == entity_attr and entity.entity_type == entity_type
        )

    def clear_mode(self):
        self.mode = Mode.UNDEFINED

    def setup(self, data):
        self.firmware = data.get('FrmVer_NIU')
        self.mode = Mode(data.get('Workmode'))
        self.entities = [
            entity.setup(data)
            for entity in Appliance._create_entities(data) if entity.attr in data
        ]

    @property
    def speed_range(self) -> tuple:
        ## Electrolux Devices: 
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

    def __init__(self, username: str, password: str, session: aiohttp.ClientSession) -> None:
        """Sample API Client."""
        self._username = username
        self._password = password
        self._session = session
        self._access_token = None
        self._token = None
        self._current_access_token = None
        self._token_expires = datetime.now()
        self.appliances = None
    
    async def _get_token(self) -> dict:
        json = {
            "clientId": CLIENT_ID,
            "clientSecret": CLIENT_SECRET,
            "grantType": "client_credentials"
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        return await self.api_wrapper("post", TOKEN_URL, json, headers)
    
    async def _login(self, access_token: str) -> dict:
        credentials = {
            "username": self._username,
            "password": self._password
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": X_API_KEY
        }
        return await self.api_wrapper("post", AUTHENTICATION_URL, credentials, headers)

    async def _get_token2(self, idToken: str, countryCode: str) -> dict:
        credentials = {
            "clientId": CLIENT_ID,
            "idToken": idToken,
            "grantType": "urn:ietf:params:oauth:grant-type:token-exchange"
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin-Country-Code": countryCode
        }
        return await self.api_wrapper("post", TOKEN_URL, credentials, headers)

    async def _get_appliances(self, access_token: str) -> dict:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": X_API_KEY
        }
        return await self.api_wrapper("get", APPLIANCES_URL, headers=headers)

    async def _get_appliance_info(self, access_token: str, pnc_id: str) -> dict:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": X_API_KEY
        }
        url = f"{APPLIANCES_URL}/{pnc_id}/info"
        return await self.api_wrapper("get", url, headers=headers)

    async def async_login(self) -> bool:
        if self._current_access_token is not None and self._token_expires > datetime.now():
            return True

        _LOGGER.debug("Current token is not set or expired")

        self._token = None
        self._current_access_token = None
        access_token = await self._get_token()

        if 'accessToken' not in access_token:
            self._access_token = None
            self._current_access_token = None
            _LOGGER.error("AccessToken 1 is missing")
            return False
        
        userToken = await self._login(access_token['accessToken'])

        if 'idToken' not in userToken:
            self._current_access_token = None
            _LOGGER.error("User login failed")
            return False

        token = await self._get_token2(userToken['idToken'], userToken['countryCode'])

        if 'accessToken' not in token:
            self._current_access_token = None
            _LOGGER.error("AccessToken 2 is missing")
            return False
        
        _LOGGER.debug("Received new token sucssfully")

        self._token_expires = datetime.now() + timedelta(seconds=token['expiresIn'])
        self._current_access_token = token['accessToken']
        return True

    async def async_get_data(self) -> Appliances:
        """Get data from the API."""
        n = 0
        while not await self.async_login() and n < RETRIES:
            _LOGGER.debug(f"Re-trying login. Attempt {n + 1} / {RETRIES}")
            n += 1

        if self._current_access_token is None:
            raise Exception("Unable to login")

        access_token = self._current_access_token
        appliances = await self._get_appliances(access_token)
        _LOGGER.debug(f"Fetched data: {appliances}")

        found_appliances = {}
        for appliance in (appliance for appliance in appliances if 'applianceId' in appliance):
            modelName = appliance['applianceData']['modelName']
            applianceId = appliance['applianceId']
            applianceName = appliance['applianceData']['applianceName']
        
            app = Appliance(applianceName, applianceId, modelName)
            appliance_info = await self._get_appliance_info(access_token, applianceId)
            _LOGGER.debug(f"Fetched data: {appliance_info}")

            app.brand = appliance_info['brand']
            app.serialNumber = appliance_info['serialNumber']
            app.device = appliance_info['deviceType']

            if app.device != 'AIR_PURIFIER':
                continue

            data = appliance.get('properties', {}).get('reported', {})
            data['status'] = appliance.get('connectionState')
            data['connectionState'] = appliance.get('connectionState')
            app.setup(data)

            found_appliances[app.pnc_id] = app

        return Appliances(found_appliances)

    async def set_fan_speed(self, pnc_id: str, level: int):
        data = {
            "Fanspeed": level
        }
        result = await self._send_command(self._current_access_token, pnc_id, data)
        _LOGGER.debug(f"Set Fan Speed: {result}")

    async def set_work_mode(self, pnc_id: str, mode: Mode):
        data = {
            "WorkMode": mode
        }
        result = await self._send_command(self._current_access_token, pnc_id, data)
        _LOGGER.debug(f"Set Fan Speed: {result}")

    async def _send_command(self, access_token: str, pnc_id: str, command: dict) -> None:
        """Get data from the API."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": X_API_KEY
        }

        await self.api_wrapper("put", f"{APPLIANCES_URL}/{pnc_id}/command", data=command, headers=headers)

    async def api_wrapper(self, method: str, url: str, data: dict = {}, headers: dict = {}) -> dict:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                if method == "get":
                    response = await self._session.get(url, headers=headers)
                    return await response.json()
                elif method == "put":
                    response = await self._session.put(url, headers=headers, json=data)
                    return await response.json()
                elif method == "post":
                    response = await self._session.post(url, headers=headers, json=data)
                    return await response.json()
                else:
                    raise Exception("Unsupported http method '%s'" % method)

        except asyncio.TimeoutError as exception:
            _LOGGER.error(
                "Timeout error fetching information from %s - %s",
                url,
                exception,
            )

        except (KeyError, TypeError) as exception:
            _LOGGER.error(
                "Error parsing information from %s - %s",
                url,
                exception,
            )
        except (aiohttp.ClientError, socket.gaierror) as exception:
            _LOGGER.error(
                "Error fetching information from %s - %s",
                url,
                exception,
            )
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("Something really wrong happened! - %s", exception)

        return {}
