"""TTS platform for Freya text-cleaning proxy.
Freya 纯文本清洗 TTS 代理平台。
"""

from __future__ import annotations

from typing import Any

try:
    from homeassistant.components.tts import DATA_COMPONENT
except ImportError:
    from homeassistant.components.tts.const import DOMAIN as TTS_DOMAIN

    DATA_COMPONENT = TTS_DOMAIN

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_TTS_PROXY_TARGET, DOMAIN, LOGGER
from .util import clean_plain_text


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Freya clean-text TTS proxy entity."""
    target_tts = entry.data.get(CONF_TTS_PROXY_TARGET, "")
    async_add_entities([FreyaCleanTextTtsEntity(entry, target_tts)])


class FreyaCleanTextTtsEntity(TextToSpeechEntity):
    """Text-to-speech proxy entity that cleans text before forwarding."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        entry: ConfigEntry,
        target_entity_id: str,
    ) -> None:
        """Initialize the TTS proxy entity."""
        self.entry = entry
        self._target_entity_id = target_entity_id
        self._attr_unique_id = f"{entry.entry_id}_tts"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Freya",
            model="Freya AI TTS",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _get_target_entity(self) -> TextToSpeechEntity | None:
        """Retrieve the target TTS entity from entity component registry."""
        tts_component = self.hass.data.get(DATA_COMPONENT)
        if not tts_component:
            return None
        entity = tts_component.get_entity(self._target_entity_id)
        if entity is self or isinstance(entity, FreyaCleanTextTtsEntity):
            return None
        return entity if isinstance(entity, TextToSpeechEntity) else None

    @property
    def available(self) -> bool:
        """Return True if target entity is available."""
        target = self._get_target_entity()
        return target is not None and target.available

    @property
    def supported_features(self) -> int:
        """Return supported features delegated from target entity."""
        if target := self._get_target_entity():
            return target.supported_features
        return 0

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages delegated from target entity."""
        if target := self._get_target_entity():
            return target.supported_languages
        return ["*"]

    @property
    def default_language(self) -> str | None:
        """Return default language delegated from target entity."""
        if target := self._get_target_entity():
            return target.default_language
        return self.hass.config.language

    @property
    def supported_options(self) -> list[str] | None:
        """Return supported options delegated from target entity."""
        if target := self._get_target_entity():
            return target.supported_options
        return None

    @property
    def default_options(self) -> dict[str, Any] | None:
        """Return default options delegated from target entity."""
        if target := self._get_target_entity():
            return target.default_options
        return None

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any] | None = None,
    ) -> TtsAudioType:
        """Clean message formatting and forward to target TTS entity."""
        cleaned_text = clean_plain_text(message)
        if not cleaned_text:
            LOGGER.debug("TTS message is empty after cleaning, skipping generation")
            return (None, None)

        target = self._get_target_entity()
        if not target:
            LOGGER.error("Target TTS entity %s is not available", self._target_entity_id)
            return (None, None)

        return await target.async_get_tts_audio(
            cleaned_text,
            language,
            options or {},
        )
