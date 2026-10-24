"""TTS proxy config flow and options flow helper.
Freya TTS 代理配置流与选项流辅助模块。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)

from .const import (
    CONF_ENTRY_TYPE,
    CONF_PENDING_TTS_PROXY,
    CONF_TTS_PROXY_TARGET,
    DOMAIN,
    ENTRY_TYPE_TTS_PROXY,
)


def async_has_any_tts_entities(hass: HomeAssistant) -> bool:
    """Check if there are any non-Freya TTS entities in the system."""
    ent_reg = er.async_get(hass)
    for state in hass.states.async_all("tts"):
        entity_entry = ent_reg.async_get(state.entity_id)
        if entity_entry and entity_entry.platform == DOMAIN:
            continue
        return True
    return False


def async_get_available_tts_entities(
    hass: HomeAssistant,
    exclude_entry_id: str | None = None,
) -> list[str]:
    """Retrieve available TTS entity IDs excluding Freya's own proxies and already bound targets."""
    ent_reg = er.async_get(hass)
    configured_targets: set[str] = set()
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == exclude_entry_id:
            continue
        if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_TTS_PROXY:
            if target := entry.data.get(CONF_TTS_PROXY_TARGET):
                configured_targets.add(target)

    available_entities: list[str] = []
    for state in hass.states.async_all("tts"):
        entity_entry = ent_reg.async_get(state.entity_id)
        if entity_entry and entity_entry.platform == DOMAIN:
            continue
        if state.entity_id in configured_targets:
            continue
        available_entities.append(state.entity_id)
    return available_entities


def async_suggest_tts_proxy_name(hass: HomeAssistant, target_entity_id: str) -> str:
    """Generate a default display name based on the target TTS entity."""
    clean_name: str | None = None
    if entity_entry := er.async_get(hass).async_get(target_entity_id):
        clean_name = entity_entry.name or entity_entry.original_name

    if not clean_name and (state := hass.states.get(target_entity_id)):
        clean_name = state.attributes.get("friendly_name") or state.name

    clean_name = clean_name or target_entity_id.split(".")[-1].replace("_", " ").title()
    return f"Freya AI - {clean_name}"


if TYPE_CHECKING:
    _BaseMixin = config_entries.ConfigFlow
else:
    _BaseMixin = object


class FreyaTtsFlowMixin(_BaseMixin):
    """Mixin providing TTS proxy config flow steps for FreyaFlowHandler."""

    _pending_service_data: dict[str, Any] | None

    async def async_step_tts_proxy_optional(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Prompt user for optional clean-text TTS proxy setup."""
        available_tts = async_get_available_tts_entities(self.hass)
        pending_service = getattr(self, "_pending_service_data", None)
        if not available_tts or not pending_service:
            return self.async_create_entry(title="Freya AI Conversation", data=pending_service or {})

        if user_input is not None:
            target_tts = user_input.get(CONF_TTS_PROXY_TARGET)
            final_data = dict(pending_service)
            if target_tts and target_tts != "none":
                final_data[CONF_PENDING_TTS_PROXY] = {
                    CONF_TTS_PROXY_TARGET: target_tts,
                }

            return self.async_create_entry(
                title="Freya AI Conversation",
                data=final_data,
            )

        schema = vol.Schema(
            {
                vol.Optional(CONF_TTS_PROXY_TARGET): EntitySelector(
                    EntitySelectorConfig(
                        domain="tts",
                        include_entities=available_tts,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="tts_proxy_optional",
            data_schema=schema,
        )

    async def async_step_tts_init(
        self,
        user_input: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Create TTS proxy entry initiated from service setup."""
        target_tts = user_input[CONF_TTS_PROXY_TARGET]
        await self.async_set_unique_id(f"{DOMAIN}_tts_{target_tts}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=async_suggest_tts_proxy_name(self.hass, target_tts),
            data={
                CONF_ENTRY_TYPE: ENTRY_TYPE_TTS_PROXY,
                CONF_TTS_PROXY_TARGET: target_tts,
            },
        )

    async def async_step_tts_proxy_add(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle standalone TTS proxy creation flow."""
        available_tts = async_get_available_tts_entities(self.hass)
        if not available_tts:
            if async_has_any_tts_entities(self.hass):
                return self.async_abort(reason="all_tts_configured")
            return self.async_abort(reason="no_tts_available")

        if user_input is not None:
            target_tts = user_input[CONF_TTS_PROXY_TARGET]
            await self.async_set_unique_id(f"{DOMAIN}_tts_{target_tts}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=async_suggest_tts_proxy_name(self.hass, target_tts),
                data={
                    CONF_ENTRY_TYPE: ENTRY_TYPE_TTS_PROXY,
                    CONF_TTS_PROXY_TARGET: target_tts,
                },
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TTS_PROXY_TARGET,
                    default=available_tts[0],
                ): EntitySelector(
                    EntitySelectorConfig(
                        domain="tts",
                        include_entities=available_tts,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="tts_proxy_add",
            data_schema=schema,
        )

    async def async_step_tts_proxy_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguring an existing TTS proxy entry."""
        reconfigure_entry = self._get_reconfigure_entry()
        available_tts = async_get_available_tts_entities(
            self.hass, exclude_entry_id=reconfigure_entry.entry_id
        )

        current_target = reconfigure_entry.data.get(CONF_TTS_PROXY_TARGET, "")

        selectable_tts = list(available_tts)
        if current_target and current_target not in selectable_tts:
            selectable_tts.append(current_target)

        if not selectable_tts:
            return self.async_abort(reason="no_tts_available")

        if user_input is not None:
            target_tts = user_input[CONF_TTS_PROXY_TARGET]
            new_unique_id = f"{DOMAIN}_tts_{target_tts}"

            if target_tts != current_target:
                await self.async_set_unique_id(new_unique_id)
                self._abort_if_unique_id_configured()

            updated_data = {
                CONF_ENTRY_TYPE: ENTRY_TYPE_TTS_PROXY,
                CONF_TTS_PROXY_TARGET: target_tts,
            }

            return self.async_update_reload_and_abort(
                reconfigure_entry,
                title=async_suggest_tts_proxy_name(self.hass, target_tts),
                unique_id=new_unique_id,
                data=updated_data,
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TTS_PROXY_TARGET,
                    default=current_target if current_target in selectable_tts else selectable_tts[0],
                ): EntitySelector(
                    EntitySelectorConfig(
                        domain="tts",
                        include_entities=selectable_tts,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="tts_proxy_reconfigure",
            data_schema=schema,
        )
