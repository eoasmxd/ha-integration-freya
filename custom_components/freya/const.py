"""Constants for the Freya integration.
Freya 集成常量。
"""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "freya"
CONF_URL = "url"
CONF_PASSWORD = "password"
CONF_IS_ADDON = "is_addon"
SERVICE_CHAT = "chat"
