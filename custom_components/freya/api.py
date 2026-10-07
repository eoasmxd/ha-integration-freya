"""Freya WebSocket communication client.
Freya WebSocket 通信客户端。
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

import aiohttp
from yarl import URL

LOGGER = logging.getLogger(__name__)

CLIENT_ID_PREFIX = "homeassistant"
CHANNEL_TYPE = "homeassistant"


class FreyaApiClientError(Exception):
    """Base exception for Freya API client.
    Freya API 客户端基础异常。
    """


class FreyaApiClientCommunicationError(FreyaApiClientError):
    """Exception raised when communication with Freya fails.
    与 Freya 通信失败时引发的异常。
    """


class FreyaApiClient:
    """Client for communicating with the Freya WebSocket service.
    与 Freya WebSocket 服务通信的客户端。
    """

    def __init__(
        self,
        url: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the client and normalize the WebSocket URL.
        初始化客户端并标准化 WebSocket 地址。
        """
        if url.startswith("http://"):
            url = f"ws://{url[7:]}"
        elif url.startswith("https://"):
            url = f"wss://{url[8:]}"
        elif not url.startswith(("ws://", "wss://")):
            url = f"ws://{url}"
        self._url = url.rstrip("/")
        self._session = session
        self._client_id = f"{CLIENT_ID_PREFIX}:{uuid.uuid4().hex[:8]}"

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._listen_task: asyncio.Task | None = None
        self._closed = False
        self._connected_event = asyncio.Event()
        self._pending_futures: dict[str, asyncio.Future[str]] = {}
        self._pending_deltas: dict[str, list[str]] = {}

    def _build_ws_url(self) -> str:
        """Build the complete WebSocket URL with query parameters.
        构建携带客户端查询参数的完整 WebSocket URL。
        """
        return str(
            URL(self._url).update_query(
                {
                    "clientId": self._client_id,
                    "channelType": CHANNEL_TYPE,
                    "sessionId": f"{CLIENT_ID_PREFIX}:main",
                }
            )
        )

    async def async_connect(self) -> None:
        """Start the background WebSocket maintenance task.
        启动常驻 WebSocket 连接后台维护任务。
        """
        if self._listen_task is None or self._listen_task.done():
            self._closed = False
            self._listen_task = asyncio.create_task(self._connection_loop())

    async def _connection_loop(self) -> None:
        """Maintain persistent WebSocket connection with auto-reconnect.
        后台维持 WebSocket 长连接并在断开时自动重连。
        """
        while not self._closed:
            try:
                ws_url = self._build_ws_url()
                async with self._session.ws_connect(ws_url, autoping=True) as ws:
                    self._ws = ws
                    await ws.send_json(
                        {
                            "event": "client:reconnect",
                            "data": {
                                "clientId": self._client_id,
                                "channelType": CHANNEL_TYPE,
                            },
                        }
                    )

                    async for msg in ws:
                        if msg.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break

                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue

                        self._handle_incoming_message(msg.data)

            except asyncio.CancelledError:
                break
            except Exception as err:
                LOGGER.debug("Freya WebSocket connection exception: %s", err)
            finally:
                self._ws = None
                self._connected_event.clear()
                for future in self._pending_futures.values():
                    if not future.done():
                        future.set_exception(
                            FreyaApiClientCommunicationError("Freya connection unexpectedly closed")
                        )
                self._pending_futures.clear()
                self._pending_deltas.clear()

            if not self._closed:
                await asyncio.sleep(3)

    def _handle_incoming_message(self, data_str: str) -> None:
        """Parse incoming server messages and dispatch results.
        解析服务端消息并派发结果。
        """
        try:
            payload = json.loads(data_str)
        except json.JSONDecodeError:
            return

        event = payload.get("event")
        data = payload.get("data") or {}

        if event in ("server:connected", "server:reconnected"):
            self._connected_event.set()
            LOGGER.debug("Freya WebSocket handshake ready: %s", event)
            return

        session_id = data.get("sessionId")
        if not session_id or session_id not in self._pending_futures:
            return

        future = self._pending_futures[session_id]

        if event == "server:reply":
            if not future.done():
                future.set_result(str(data.get("text", "")))
        elif event == "server:delta":
            if text := data.get("text"):
                self._pending_deltas.setdefault(session_id, []).append(text)
        elif event == "server:completed":
            if not future.done():
                deltas = self._pending_deltas.get(session_id, [])
                future.set_result("".join(deltas))

    async def async_validate_connection(self) -> bool:
        """Validate WebSocket connectivity with Freya.
        验证与 Freya 的 WebSocket 连通性。
        """
        try:
            ws_url = self._build_ws_url()
            async with asyncio.timeout(10):
                async with self._session.ws_connect(ws_url, autoping=True) as ws:
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                payload = json.loads(msg.data)
                            except json.JSONDecodeError:
                                continue
                            if payload.get("event") in ("server:connected", "server:reconnected"):
                                return True
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break
            return False
        except Exception as err:
            LOGGER.debug("Freya connection validation failed: %s", err)
            raise FreyaApiClientCommunicationError(err) from err

    async def async_send_message(self, data: Any) -> str:
        """Send a message to Freya and await the final reply text.
        发送消息至 Freya 并等待最终回复文本。
        """
        await self.async_connect()

        try:
            async with asyncio.timeout(10):
                await self._connected_event.wait()
        except TimeoutError as err:
            raise FreyaApiClientCommunicationError("Freya service is not connected") from err

        if isinstance(data, dict):
            payload_data = dict(data)
        else:
            payload_data = {"content": str(data)}

        raw_session_id = payload_data.get("sessionId")
        if raw_session_id:
            session_id = (
                str(raw_session_id)
                if str(raw_session_id).startswith(f"{CLIENT_ID_PREFIX}:")
                else f"{CLIENT_ID_PREFIX}:{raw_session_id}"
            )
            ephemeral = payload_data.get("ephemeral", False)
        else:
            session_id = f"{CLIENT_ID_PREFIX}:temp:{uuid.uuid4().hex[:8]}"
            ephemeral = True

        payload_data["sessionId"] = session_id
        payload_data["ephemeral"] = ephemeral

        if not self._ws or self._ws.closed:
            raise FreyaApiClientCommunicationError("Freya WebSocket connection is closed")

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_futures[session_id] = future
        self._pending_deltas[session_id] = []

        try:
            await self._ws.send_json(
                {
                    "event": "client:message",
                    "data": payload_data,
                }
            )

            async with asyncio.timeout(120):
                return await future

        except (TimeoutError, asyncio.CancelledError) as err:
            if self._ws and not self._ws.closed:
                try:
                    await self._ws.send_json(
                        {
                            "event": "client:interrupt",
                            "data": {"sessionId": session_id},
                        }
                    )
                except Exception:
                    pass
            if isinstance(err, TimeoutError):
                raise FreyaApiClientCommunicationError("Timed out waiting for response from Freya") from err
            raise
        finally:
            self._pending_futures.pop(session_id, None)
            self._pending_deltas.pop(session_id, None)

    async def async_close(self) -> None:
        """Close the WebSocket connection and release resources.
        关闭长连接并释放后台任务资源。
        """
        self._closed = True
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        if self._ws and not self._ws.closed:
            await self._ws.close()

