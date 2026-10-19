"""Conversation platform for Freya.
Freya 对话平台。
"""

from __future__ import annotations

from typing import Literal

from homeassistant.components.conversation import (
    ConversationEntity,
    ConversationEntityFeature,
    ConversationInput,
    ConversationResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import ulid

from .const import DOMAIN, LOGGER
from .data import FreyaConfigEntry
from .util import clean_plain_text


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreyaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freya conversation entity.
    设置 Freya 对话平台实体。
    """
    async_add_entities([FreyaConversationEntity(entry)])


class FreyaConversationEntity(ConversationEntity):
    """Freya conversation agent entity.
    Freya 对话代理实体。
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_suggested_object_id = DOMAIN
    _attr_supported_features = ConversationEntityFeature.CONTROL

    def __init__(self, entry: FreyaConfigEntry) -> None:
        """Initialize the conversation entity.
        初始化对话实体。
        """
        self.entry = entry
        self._attr_unique_id = DOMAIN
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or "Freya",
            manufacturer="Freya",
            model="Freya AI Agent",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return supported languages.
        返回支持的语言列表。
        """
        return "*"

    async def async_process(
        self, user_input: ConversationInput
    ) -> ConversationResult:
        """Process a conversation user input.
        处理用户对话输入并向 Agent 转发。
        """
        client = self.entry.runtime_data.client
        conversation_id = user_input.conversation_id or ulid.ulid_now()

        intent_response = intent.IntentResponse(language=user_input.language)

        try:
            payload = {
                "content": user_input.text,
                "sessionId": conversation_id,
                "language": user_input.language,
            }

            chat_res = await client.async_send_message(payload)
            response_text = chat_res.text
            if user_input.device_id or user_input.satellite_id:
                response_text = clean_plain_text(response_text)
            intent_response.async_set_speech(response_text)
            if chat_res.attachments:
                intent_response.data["attachments"] = chat_res.attachments

        except Exception as err:
            LOGGER.exception("Exception occurred while processing Freya conversation: %s", err)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Failed to request Freya: {err}",
            )

        return ConversationResult(
            response=intent_response,
            conversation_id=conversation_id,
        )
