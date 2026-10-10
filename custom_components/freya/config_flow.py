"""Config flow for Freya integration.
Freya 配置流向导。
"""

from __future__ import annotations

from typing import Any

from awesomeversion import AwesomeVersion
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .api import (
    FreyaApiClient,
    FreyaApiClientAuthenticationError,
    FreyaApiClientCommunicationError,
)
from .const import CONF_IS_ADDON, CONF_PASSWORD, CONF_URL, DOMAIN, LOGGER

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

        addons = get_apps_list(hass) or []
        for app in addons:
            if not isinstance(app, dict):
                continue
            slug = app.get("slug", "")
            if slug == "freya" or slug.endswith("_freya"):
                state = str(app.get("state", "unknown")).lower()
                return {
                    "slug": slug,
                    "name": app.get("name", "Freya"),
                    "state": state,
                    "version": app.get("version"),
                    "hostname": slug.replace("_", "-"),
                }
    except Exception as err:
        LOGGER.error("Failed to get installed app information: %s", err)

    return None


class FreyaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Freya.
    Freya UI 配置流处理器。
    """

    VERSION = 1
    _addon_slug: str | None = None
    _internal_url: str | None = None

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
            return self.async_create_entry(
                title="Freya",
                data={
                    CONF_URL: self._internal_url,
                    CONF_PASSWORD: "",
                    CONF_IS_ADDON: True,
                },
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
        return await self._async_handle_addon_connection()

    async def _async_handle_addon_connection(
        self,
    ) -> config_entries.ConfigFlowResult:
        """Handle connection verification and entry creation or update.
        统一处理 Freya 应用的状态检测、连通性验证与入口创建或更新。
        """
        if "hassio" not in self.hass.config.components:
            return await self.async_step_manual_config()

        freya_addon = await _async_find_freya_addon(self.hass)

        if self.source == config_entries.SOURCE_RECONFIGURE:
            reconfigure_entry = self._get_reconfigure_entry()
            is_addon_before = reconfigure_entry.data.get(CONF_IS_ADDON, False)
            if not is_addon_before or freya_addon is None:
                return await self.async_step_manual_config()

        if freya_addon is None:
            return await self.async_step_choose_install()

        self._addon_slug = freya_addon["slug"]

        if freya_addon["state"] != "started":
            return await self.async_step_not_running()

        internal_url = f"http://{freya_addon['hostname']}:3000"

        client = FreyaApiClient(internal_url, async_get_clientsession(self.hass))
        try:
            await client.async_validate_connection()
        except FreyaApiClientCommunicationError:
            return await self.async_step_cannot_connect()

        if self.source == config_entries.SOURCE_RECONFIGURE:
            reconfigure_entry = self._get_reconfigure_entry()
            return self.async_update_reload_and_abort(
                reconfigure_entry,
                data={
                    **reconfigure_entry.data,
                    CONF_URL: internal_url,
                    CONF_PASSWORD: "",
                    CONF_IS_ADDON: True,
                },
            )

        return self.async_create_entry(
            title="Freya",
            data={
                CONF_URL: internal_url,
                CONF_PASSWORD: "",
                CONF_IS_ADDON: True,
            },
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

            client = FreyaApiClient(url, async_get_clientsession(self.hass), password)
            try:
                await client.async_validate_connection()
                if self.source == config_entries.SOURCE_RECONFIGURE:
                    reconfigure_entry = self._get_reconfigure_entry()
                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        data={
                            **reconfigure_entry.data,
                            CONF_URL: url,
                            CONF_PASSWORD: password,
                            CONF_IS_ADDON: False,
                        },
                    )
                return self.async_create_entry(
                    title="Freya",
                    data={
                        CONF_URL: url,
                        CONF_PASSWORD: password,
                        CONF_IS_ADDON: False,
                    },
                )
            except FreyaApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except FreyaApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"

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
