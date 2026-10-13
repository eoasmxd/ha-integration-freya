"""Custom types and data classes for Freya integration.
Freya 集成自定义类型与数据类。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.loader import Integration

from .api import FreyaApiClient


@dataclass(slots=True)
class FreyaChatResponse:
    """Freya chat response data container.
    Freya 对话响应数据容器。
    """

    text: str
    attachments: list[dict[str, Any]] = field(default_factory=list)

    def to_service_response(self) -> dict[str, Any]:
        """Convert to service response dictionary.
        转换为服务响应字典。
        """
        response: dict[str, Any] = {
            "text": self.text,
        }
        if self.attachments:
            response["attachments"] = self.attachments
        return response


@dataclass
class FreyaData:
    """Runtime data container for Freya.
    Freya 运行时数据容器。
    """

    client: FreyaApiClient
    integration: Integration


FreyaConfigEntry = ConfigEntry[FreyaData]
