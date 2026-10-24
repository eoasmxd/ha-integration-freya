"""Config flow for Freya integration.
Freya 配置流向导。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from awesomeversion import AwesomeVersion
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .api import (
    FreyaApiClient,
    FreyaApiClientAuthenticationError,
    FreyaApiClientCommunicationError,
    FreyaApiClientIncompatibleVersionError,
)
from .const import (
    CONF_ENTRY_TYPE,
    CONF_IS_ADDON,
    CONF_PASSWORD,
    CONF_URL,
    DOMAIN,
    ENTRY_TYPE_SERVICE,
    ENTRY_TYPE_TTS_PROXY,
    LOGGER,
)
from .tts_flow import (
    FreyaTtsFlowMixin,
    async_get_available_tts_entities,
)

MIN_HA_VERSION = "2026.2.0"

ADDON_REPO_URL = "https://github.com/eoasmxd/ha-addons"
ADDON_REPO_BADGE = (
    "[![Add repository to Home Assistant]"
    "(https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)]"
    "(https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Feoasmxd%2Fha-addons)"
)


async def _async_find_freya_addon(hass: HomeAssistant) -> dict[str, Any] | None:
    """Find the installed Freya app and get its current status.
    查找已安装的 Freya 应用并获取最新状态。
    """
    try:
        try:
            from homeassistant.components.hassio import get_apps_list
        except ImportError:
            from homeassistant.components.hassio import get_addons_list as get_apps_list

        candidates = []
        addons = get_apps_list(hass) or []
        for app in addons:
            if not isinstance(app, dict):
                continue
            slug = app.get("slug", "")
            is_stable = slug == "freya" or slug.endswith("_freya")
            is_edge = slug == "freya_edge" or slug.endswith("_freya_edge")
            if is_stable or is_edge:
                state = str(app.get("state", "unknown")).lower()
                candidates.append(
                    {
                        "info": {
                            "slug": slug,
                            "name": app.get("name", "Freya"),
                            "state": state,
                            "version": app.get("version"),
                            "hostname": slug.replace("_", "-"),
                        },
                        "is_started": state == "started",
                        "is_stable": is_stable,
                    }
                )

        if candidates:
            candidates.sort(key=lambda x: (x["is_started"], x["is_stable"]), reverse=True)
            return candidates[0]["info"]

    except Exception as err:
        LOGGER.error("Failed to get installed app information: %s", err)

    return None


async def _async_validate_service_connection(
    hass: HomeAssistant,
    url: str,
    password: str | None = None,
) -> dict[str, str]:
    """Validate connection to Freya server and return errors mapping if any."""
    client = FreyaApiClient(url, async_get_clientsession(hass), password)
    try:
        await client.async_validate_connection()
        return {}
    except FreyaApiClientAuthenticationError:
        return {"base": "invalid_auth"}
    except FreyaApiClientIncompatibleVersionError:
        return {"base": "incompatible_version"}
    except FreyaApiClientCommunicationError:
        return {"base": "cannot_connect"}
    except Exception:
        return {"base": "unknown"}


async def _async_resolve_addon_service(
    hass: HomeAssistant,
) -> tuple[str, dict[str, Any] | None, str | None, dict[str, str]]:
    """Resolve and validate Freya Add-on deployment status and endpoint."""
    if "hassio" not in hass.config.components:
        return ("not_hassio", None, None, {})

    freya_addon = await _async_find_freya_addon(hass)
    if freya_addon is None:
        return ("not_installed", None, None, {})

    if freya_addon["state"] != "started":
        return ("not_running", freya_addon, None, {})

    internal_url = f"http://{freya_addon['hostname']}:3000"
    errors = await _async_validate_service_connection(hass, internal_url, "")
    return ("ready", freya_addon, internal_url, errors)


class FreyaFlowHandler(FreyaTtsFlowMixin, config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Freya.
    Freya UI 配置流处理器。
    """

    VERSION = 1
    _addon_slug: str | None = None
    _internal_url: str | None = None
    _pending_service_data: dict[str, Any] | None = None

    async def async_step_hassio(
        self,
        discovery_info: HassioServiceInfo,
    ) -> config_entries.ConfigFlowResult:
        """Handle discovery flow from Supervisor.
        处理 Supervisor 广播的自动发现流程。
        """
        await self.async_set_unique_id(DOMAIN)
        self.context["title_placeholders"] = {"name": "Freya"}
        slug = discovery_info.slug
        host = discovery_info.config.get("host") or slug.replace("_", "-")
        port = discovery_info.config.get("port", 3000)
        self._internal_url = f"http://{host}:{port}"
        self._abort_if_unique_id_configured(
            updates={
                CONF_URL: self._internal_url,
                CONF_PASSWORD: "",
                CONF_IS_ADDON: True,
            }
        )

        client = FreyaApiClient(self._internal_url, async_get_clientsession(self.hass))
        try:
            await client.async_validate_connection()
        except FreyaApiClientIncompatibleVersionError:
            return self.async_abort(reason="incompatible_version")
        except FreyaApiClientCommunicationError:
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Confirm discovery step with the user.
        处理用户对自动发现的确认。
        """
        if user_input is not None:
            return await self._async_finish_service_setup(
                {
                    CONF_URL: self._internal_url,
                    CONF_PASSWORD: "",
                    CONF_IS_ADDON: True,
                }
            )

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": "Freya"},
        )

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step invoked by the user.
        处理用户手动发起的初次配置步骤。
        """
        if AwesomeVersion(HA_VERSION) < AwesomeVersion(MIN_HA_VERSION):
            return self.async_abort(reason="unsupported_ha_version")

        has_service = any(
            entry.data.get(CONF_ENTRY_TYPE, ENTRY_TYPE_SERVICE) == ENTRY_TYPE_SERVICE
            for entry in self._async_current_entries()
        )
        if has_service:
            return await self.async_step_tts_proxy_add()

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        return await self._async_handle_addon_connection()

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a reconfiguration flow.
        处理重新配置流程。
        """
        reconfigure_entry = self._get_reconfigure_entry()
        if reconfigure_entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_TTS_PROXY:
            return await self.async_step_tts_proxy_reconfigure(user_input)
        return await self._async_handle_addon_connection()

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Handle initiation of re-authentication.
        处理重新认证流程的触发。
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle confirmation of re-authentication.
        处理重新认证密码确认。
        """
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            password = user_input.get(CONF_PASSWORD, "")
            url = reauth_entry.data[CONF_URL]
            errors = await _async_validate_service_connection(self.hass, url, password)
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PASSWORD, default=reauth_entry.data.get(CONF_PASSWORD) or ""): str,
                }
            ),
            description_placeholders={"url": reauth_entry.data.get(CONF_URL, "")},
            errors=errors,
        )

    async def _async_handle_addon_connection(
        self,
    ) -> config_entries.ConfigFlowResult:
        """Handle connection verification and entry creation or update.
        统一处理 Freya 应用的状态检测、连通性验证与入口创建或更新。
        """
        status, addon_info, internal_url, errors = await _async_resolve_addon_service(self.hass)

        if status == "not_hassio":
            return await self.async_step_manual_config()

        if self.source == config_entries.SOURCE_RECONFIGURE:
            reconfigure_entry = self._get_reconfigure_entry()
            is_addon_before = reconfigure_entry.data.get(CONF_IS_ADDON, False)
            if not is_addon_before or status == "not_installed":
                return await self.async_step_manual_config()

        if status == "not_installed":
            return await self.async_step_choose_install()

        self._addon_slug = addon_info["slug"]

        if status == "not_running":
            return await self.async_step_not_running()

        if errors.get("base") == "incompatible_version":
            return self.async_abort(reason="incompatible_version")
        if errors:
            return await self.async_step_cannot_connect()

        return await self._async_finish_service_setup(
            {
                CONF_URL: internal_url,
                CONF_PASSWORD: "",
                CONF_IS_ADDON: True,
            }
        )

    async def async_step_choose_install(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Menu to choose between add-on install or manual config.
        未发现应用时，引导选择安装应用或手动配置外部服务。
        """
        return self.async_show_menu(
            step_id="choose_install",
            menu_options=["install_addon", "manual_config"],
        )

    async def async_step_manual_config(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle manual configuration for external Freya app.
        处理外部 Freya 应用的手动配置。
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL]
            password = user_input.get(CONF_PASSWORD, "")
            errors = await _async_validate_service_connection(self.hass, url, password)
            if not errors:
                return await self._async_finish_service_setup(
                    {
                        CONF_URL: url,
                        CONF_PASSWORD: password,
                        CONF_IS_ADDON: False,
                    }
                )

        default_url = ""
        default_password = ""
        if self.source == config_entries.SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            default_url = entry.data.get(CONF_URL, "")
            default_password = entry.data.get(CONF_PASSWORD, "")

        return self.async_show_form(
            step_id="manual_config",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=default_url): str,
                    vol.Optional(CONF_PASSWORD, default=default_password): str,
                }
            ),
            errors=errors,
        )

    async def async_step_install_addon(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Guide the user to install the Freya app.
        引导用户安装 Freya 应用。
        """
        if user_input is not None:
            return await self._async_handle_addon_connection()

        return self.async_show_form(
            step_id="install_addon",
            description_placeholders={
                "addon_badge": ADDON_REPO_BADGE,
                "repo_url": ADDON_REPO_URL,
            },
        )

    async def async_step_not_running(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Guide the user to start the Freya app.
        引导用户启动 Freya 应用。
        """
        if user_input is not None:
            return await self._async_handle_addon_connection()

        app_info_url = (
            f"/config/app/{self._addon_slug}/info"
            if self._addon_slug
            else "/config/apps/installed"
        )

        return self.async_show_form(
            step_id="not_running",
            description_placeholders={"app_info_url": app_info_url},
        )

    async def async_step_cannot_connect(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Guide the user when connection to the app fails.
        引导用户排查连接失败并支持重试。
        """
        if user_input is not None:
            return await self._async_handle_addon_connection()

        app_info_url = (
            f"/config/app/{self._addon_slug}/info"
            if self._addon_slug
            else "/config/apps/installed"
        )

        return self.async_show_form(
            step_id="cannot_connect",
            description_placeholders={"app_info_url": app_info_url},
        )

    async def _async_finish_service_setup(
        self,
        service_data: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Finish service configuration and create service entry."""
        if self.source == config_entries.SOURCE_RECONFIGURE:
            reconfigure_entry = self._get_reconfigure_entry()
            return self.async_update_reload_and_abort(
                reconfigure_entry,
                data={
                    **reconfigure_entry.data,
                    **service_data,
                    CONF_ENTRY_TYPE: ENTRY_TYPE_SERVICE,
                },
            )

        data = {**service_data, CONF_ENTRY_TYPE: ENTRY_TYPE_SERVICE}
        available_tts = async_get_available_tts_entities(self.hass)
        if not available_tts:
            return self.async_create_entry(title="Freya AI Conversation", data=data)

        self._pending_service_data = data
        return await self.async_step_tts_proxy_optional()
