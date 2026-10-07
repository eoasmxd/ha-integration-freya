"""Custom types and data classes for Freya integration.
Freya 集成自定义类型与数据类。
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.loader import Integration

from .api import FreyaApiClient


@dataclass
class FreyaData:
    """Runtime data container for Freya.
    Freya 运行时数据容器。
    """

    client: FreyaApiClient
    integration: Integration


FreyaConfigEntry = ConfigEntry[FreyaData]
