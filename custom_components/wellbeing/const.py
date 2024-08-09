"""Constants for Wellbeing."""
# Base component constants
CONFIG_FLOW_TITLE = "Electrolux Wellbeing"
NAME = "Wellbeing"
DOMAIN = "wellbeing"
DOMAIN_DATA = f"{DOMAIN}_data"

# Icons
ICON = "mdi:format-quote-close"

# Device classes
BINARY_SENSOR_DEVICE_CLASS = "connectivity"

# Platforms
BINARY_SENSOR = "binary_sensor"
SENSOR = "sensor"
SWITCH = "switch"
FAN = "fan"
SWITCH = "switch" 
PLATFORMS = [SENSOR, FAN, BINARY_SENSOR, SWITCH]

# Configuration and options
CONF_ENABLED = "enabled"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_REFRESH_TOKEN = "refresh_token"

# Defaults
DEFAULT_NAME = DOMAIN
DEFAULT_SCAN_INTERVAL = 30
