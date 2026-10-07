"""Freya integration entry point.
Freya 自定义集成入口。
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import FreyaApiClient
from .const import (
    CONF_URL,
    DOMAIN,
    SERVICE_CHAT,
)
from .data import FreyaConfigEntry, FreyaData

PLATFORMS: list[Platform] = [
    Platform.CONVERSATION,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreyaConfigEntry,
) -> bool:
    """Set up Freya from a config entry.
    初始化 Freya 配置条目。
    """
    client = FreyaApiClient(
        url=entry.data[CONF_URL],
        session=async_get_clientsession(hass),
    )

    entry.runtime_data = FreyaData(
        client=client,
        integration=async_get_loaded_integration(hass, entry.domain),
    )

    await client.async_connect()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_handle_chat(call: ServiceCall) -> ServiceResponse:
        """Handle chat service call.
        处理对话服务调用。
        """
        payload = {
            "content": call.data["content"],
            "language": call.data.get("language", hass.config.language),
        }
        if session_id := call.data.get("session_id"):
            payload["sessionId"] = session_id
        if toolboxes := call.data.get("toolboxes"):
            if isinstance(toolboxes, str):
                toolbox_list = [t.strip() for t in toolboxes.replace("，", ",").split(",") if t.strip()]
            elif isinstance(toolboxes, list):
                toolbox_list = [str(t).strip() for t in toolboxes if str(t).strip()]
            else:
                toolbox_list = []
            if toolbox_list:
                payload["toolboxes"] = toolbox_list
        if skill_id := call.data.get("skill_id"):
            payload["skillId"] = skill_id

        result = await entry.runtime_data.client.async_send_message(payload)
        return {"response": result}

    if not hass.services.has_service(DOMAIN, SERVICE_CHAT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CHAT,
            async_handle_chat,
            schema=vol.Schema(
                {
                    vol.Required("content"): cv.string,
                    vol.Optional("session_id"): cv.string,
                    vol.Optional("toolboxes"): vol.Any(cv.string, [cv.string]),
                    vol.Optional("skill_id"): cv.string,
                    vol.Optional("language"): cv.string,
                }
            ),
            supports_response=SupportsResponse.OPTIONAL,
        )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: FreyaConfigEntry,
) -> bool:
    """Unload a Freya config entry.
    卸载 Freya 配置条目。
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.async_close()
        loaded_entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if len(loaded_entries) <= 1 and hass.services.has_service(DOMAIN, SERVICE_CHAT):
            hass.services.async_remove(DOMAIN, SERVICE_CHAT)
    return unload_ok
