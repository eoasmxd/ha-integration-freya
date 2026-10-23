"""Constants for the Freya integration.
Freya 集成常量。
"""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "freya"
CONF_URL = "url"
CONF_PASSWORD = "password"
CONF_IS_ADDON = "is_addon"
CONF_ENTRY_TYPE = "entry_type"
CONF_TTS_PROXY_TARGET = "tts_proxy_target"
CONF_TTS_PROXY_NAME = "tts_proxy_name"
CONF_PENDING_TTS_PROXY = "pending_tts_proxy"
ENTRY_TYPE_SERVICE = "service"
ENTRY_TYPE_TTS_PROXY = "tts_proxy"
SERVICE_CHAT = "chat"
ISSUE_RESTART_REQUIRED = "restart_required"
NOTIFICATION_ID_UPDATE = "freya_integration_update"
