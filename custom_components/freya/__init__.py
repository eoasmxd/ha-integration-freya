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
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import (
    FreyaApiClient,
    FreyaApiClientAuthenticationError,
    FreyaApiClientCommunicationError,
    FreyaApiClientError,
    FreyaApiClientIncompatibleVersionError,
)
from .const import (
    CONF_IS_ADDON,
    CONF_PASSWORD,
    CONF_URL,
    DOMAIN,
    ISSUE_RESTART_REQUIRED,
    LOGGER,
    NOTIFICATION_ID_UPDATE,
    SERVICE_CHAT,
)
from .data import FreyaConfigEntry, FreyaData
from .util import clean_plain_text

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
    resolved_workspace = await asyncio.to_thread(workspace_dir.resolve)
    client = entry.runtime_data.client

    for item in items:
        if not item:
            continue
        if item.startswith(("http://", "https://")):
            resolved.append({"url": item})
            continue

        item_path = item

        if is_addon and not os.path.isabs(item_path):
            ws_candidate = await asyncio.to_thread((workspace_dir / item_path).resolve)
            if ws_candidate.is_relative_to(resolved_workspace) and await asyncio.to_thread(ws_candidate.is_file):
                resolved.append({"path": str(ws_candidate.relative_to(resolved_workspace)).replace("\\", "/")})
                continue

        local_path = Path(item_path if os.path.isabs(item_path) else hass.config.path(item_path))

        if is_addon:
            resolved_local = await asyncio.to_thread(local_path.resolve)
            if resolved_local.is_relative_to(resolved_workspace):
                if not await asyncio.to_thread(resolved_local.is_file):
                    LOGGER.warning("Attachment file does not exist: %s", item_path)
                    raise HomeAssistantError(
                        f"Attachment file not found: {item_path}",
                        translation_domain=DOMAIN,
                        translation_key="attachment_not_found",
                        translation_placeholders={"path": item_path},
                    )
                resolved.append({"path": str(resolved_local.relative_to(resolved_workspace)).replace("\\", "/")})
                continue

        if not await hass.async_add_executor_job(hass.config.is_allowed_path, str(local_path)):
            LOGGER.warning("Attachment file path is not allowed: %s", item_path)
            raise HomeAssistantError(
                f"Attachment file path is not allowed: {item_path}",
                translation_domain=DOMAIN,
                translation_key="attachment_not_allowed",
                translation_placeholders={"path": item_path},
            )

        if not await asyncio.to_thread(local_path.is_file):
            LOGGER.warning("Attachment file does not exist: %s", item_path)
            raise HomeAssistantError(
                f"Attachment file not found: {item_path}",
                translation_domain=DOMAIN,
                translation_key="attachment_not_found",
                translation_placeholders={"path": item_path},
            )

        if is_addon:
            safe_name = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}-{local_path.name}"
            target_cache_dir = workspace_dir / "cache" / "ha"
            await asyncio.to_thread(target_cache_dir.mkdir, parents=True, exist_ok=True)
            target_file = target_cache_dir / safe_name
            await asyncio.to_thread(shutil.copy2, str(local_path), str(target_file))
            resolved.append({"path": f"cache/ha/{safe_name}"})
        else:
            try:
                upload_res = await client.async_upload_file(str(local_path))
            except FreyaApiClientError as err:
                raise HomeAssistantError(
                    f"Failed to upload attachment {item_path}: {err}",
                    translation_domain=DOMAIN,
                    translation_key="attachment_upload_failed",
                    translation_placeholders={"path": item_path},
                ) from err
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
        on_auth_failed=lambda: entry.async_start_reauth(hass),
    )

    entry.runtime_data = FreyaData(
        client=client,
        integration=async_get_loaded_integration(hass, entry.domain),
    )

    try:
        await client.async_validate_connection()
    except FreyaApiClientAuthenticationError as err:
        raise ConfigEntryAuthFailed(f"Freya authentication failed: {err}") from err
    except FreyaApiClientIncompatibleVersionError as err:
        raise ConfigEntryError(f"Freya server version incompatible: {err}") from err
    except FreyaApiClientCommunicationError:
        pass

    await client.async_connect()

    ir.async_delete_issue(hass, DOMAIN, ISSUE_RESTART_REQUIRED)
    await hass.services.async_call(
        "persistent_notification",
        "dismiss",
        {"notification_id": NOTIFICATION_ID_UPDATE},
        blocking=False,
    )

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

        try:
            chat_response = await entry.runtime_data.client.async_send_message(payload)
        except FreyaApiClientAuthenticationError as err:
            raise HomeAssistantError(
                str(err),
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except FreyaApiClientIncompatibleVersionError as err:
            raise HomeAssistantError(
                str(err),
                translation_domain=DOMAIN,
                translation_key="incompatible_version",
            ) from err
        except FreyaApiClientCommunicationError as err:
            if "not connected" in str(err).lower():
                raise HomeAssistantError(
                    str(err),
                    translation_domain=DOMAIN,
                    translation_key="service_not_connected",
                ) from err
            if "timed out" in str(err).lower():
                raise HomeAssistantError(
                    str(err),
                    translation_domain=DOMAIN,
                    translation_key="timeout",
                ) from err
            raise HomeAssistantError(
                str(err),
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err
        except FreyaApiClientError as err:
            raise HomeAssistantError(str(err)) from err
        response_data = chat_response.to_service_response()
        if call.data.get("plain_text_output", False):
            response_data["text"] = clean_plain_text(response_data["text"])
        return response_data

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
                    vol.Optional("plain_text_output", default=False): cv.boolean,
                }
            ),
            supports_response=SupportsResponse.OPTIONAL,
        )

    if "http_view_registered" not in hass.data.setdefault(DOMAIN, {}):
        hass.http.register_view(FreyaNotifyUpdateView)
        hass.data[DOMAIN]["http_view_registered"] = True

    return True


class FreyaNotifyUpdateView(HomeAssistantView):
    """Handle internal update notifications from Freya Addon/Deployer.
    处理来自部署器的内部集成更新通知。
    """

    url = "/api/freya/notify_update"
    name = "api:freya:notify_update"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        """Handle POST request to create update repair issue."""
        hass: HomeAssistant = request.app["hass"]
        data: dict[str, Any] = await request.json() if request.can_read_body else {}
        version = data.get("version", "")
        if not version:
            loaded_entries = hass.config_entries.async_loaded_entries(DOMAIN)
            if loaded_entries:
                entry = loaded_entries[0]
                version = entry.runtime_data.integration.manifest.get("version", "")

        ir.async_create_issue(
            hass,
            domain=DOMAIN,
            issue_id=ISSUE_RESTART_REQUIRED,
            is_fixable=True,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="restart_required",
            translation_placeholders={"version": version or "latest"},
        )
        LOGGER.info("Created restart required issue via HTTP endpoint for Freya version %s", version)
        return self.json({"success": True})


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
        if len(loaded_entries) <= 1:
            if hass.services.has_service(DOMAIN, SERVICE_CHAT):
                hass.services.async_remove(DOMAIN, SERVICE_CHAT)
    return unload_ok
