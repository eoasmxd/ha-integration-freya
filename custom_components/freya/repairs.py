"""Repairs flow for Freya integration.
Freya 自定义集成修复流程向导。
"""

from __future__ import annotations

from typing import Any
import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, LOGGER


class FreyaRestartRequiredRepairFlow(RepairsFlow):
    """Handler for Freya integration restart flow.
    处理 Freya 集成更新完成后的重启流程。
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            LOGGER.info("User confirmed restart via Freya repair flow. Restarting Home Assistant...")
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
            await self.hass.services.async_call("homeassistant", "restart")
            return self.async_abort(reason="restart_in_progress")

        issue_registry = ir.async_get(self.hass)
        description_placeholders = None
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            description_placeholders = issue.translation_placeholders

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=description_placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None = None,
) -> RepairsFlow:
    """Create a repair flow."""
    return FreyaRestartRequiredRepairFlow()
