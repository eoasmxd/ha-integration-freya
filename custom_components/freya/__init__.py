"""Freya integration entry point.
Freya 自定义集成入口。
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import shutil
import time
from typing import Any
import uuid
import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import FreyaApiClient
from .const import (
    CONF_IS_ADDON,
    CONF_PASSWORD,
    CONF_URL,
    DOMAIN,
    SERVICE_CHAT,
)
from .data import FreyaConfigEntry, FreyaData

PLATFORMS: list[Platform] = [
    Platform.CONVERSATION,
]


def _is_addon_deployment(entry: FreyaConfigEntry) -> bool:
    """Check if Freya is deployed as a Home Assistant Add-on.
    根据安装配置判断 Freya 是否为 Home Assistant 加载项部署。
    """
    return bool(entry.data.get(CONF_IS_ADDON, False))


async def _async_resolve_attachments(
    hass: HomeAssistant,
    entry: FreyaConfigEntry,
    raw_attachments: str | list[str],
) -> list[dict[str, str]]:
    """Resolve attachment items into Freya attachments."""
    items: list[str] = []
    if isinstance(raw_attachments, str):
        for line in raw_attachments.replace("，", ",").splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith(("http://", "https://")):
                items.append(line_str)
                continue
            for part in line_str.split(","):
                if val := part.strip():
                    items.append(val)
    elif isinstance(raw_attachments, (list, tuple)):
        items.extend(str(item).strip() for item in raw_attachments if str(item).strip())

    resolved: list[dict[str, str]] = []
    is_addon = _is_addon_deployment(entry)
    workspace_dir = Path(hass.config.path("freya", "workspace"))
    resolved_workspace = workspace_dir.resolve()
    client = entry.runtime_data.client

    for item in items:
        if not item:
            continue
        if item.startswith(("http://", "https://")):
            resolved.append({"url": item})
            continue

        item_path = item

        if is_addon and not os.path.isabs(item_path):
            ws_candidate = (workspace_dir / item_path).resolve()
            if ws_candidate.is_relative_to(resolved_workspace) and await asyncio.to_thread(ws_candidate.is_file):
                resolved.append({"path": str(ws_candidate.relative_to(resolved_workspace)).replace("\\", "/")})
                continue

        local_path = Path(item_path if os.path.isabs(item_path) else hass.config.path(item_path))
        if not await asyncio.to_thread(local_path.is_file):
            continue

        if is_addon:
            resolved_local = local_path.resolve()
            if resolved_local.is_relative_to(resolved_workspace):
                resolved.append({"path": str(resolved_local.relative_to(resolved_workspace)).replace("\\", "/")})
                continue

            safe_name = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}-{local_path.name}"
            target_cache_dir = workspace_dir / "cache" / "ha"
            await asyncio.to_thread(target_cache_dir.mkdir, parents=True, exist_ok=True)
            target_file = target_cache_dir / safe_name
            await asyncio.to_thread(shutil.copy2, str(local_path), str(target_file))
            resolved.append({"path": f"cache/ha/{safe_name}"})
        else:
            upload_res = await client.async_upload_file(str(local_path))
            if remote_path := upload_res.get("path"):
                resolved.append({"path": remote_path})

    return resolved


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
        password=entry.data.get(CONF_PASSWORD),
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

        if attachments := call.data.get("attachments"):
            resolved = await _async_resolve_attachments(hass, entry, attachments)
            if resolved:
                payload["attachments"] = resolved

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
                    vol.Optional("attachments"): vol.Any(cv.string, [cv.string]),
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
