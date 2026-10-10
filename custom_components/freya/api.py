"""Freya WebSocket communication client.
Freya WebSocket 通信客户端。
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import quote
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


class FreyaApiClientAuthenticationError(FreyaApiClientError):
    """Exception raised when authentication fails.
    鉴权失败或密码错误时引发的异常。
    """


class FreyaApiClient:
    """Client for communicating with the Freya WebSocket service.
    与 Freya WebSocket 服务通信的客户端。
    """

    def __init__(
        self,
        url: str,
        session: aiohttp.ClientSession,
        password: str | None = None,
    ) -> None:
        """Initialize the client and parse base URLs.
        初始化客户端并解析基础通信地址。
        """
        base_url = url.rstrip("/")
        if not base_url.startswith(("http://", "https://", "ws://", "wss://")):
            base_url = f"http://{base_url}"

        parsed = URL(base_url)
        url_path = parsed.path.rstrip("/")
        if url_path.endswith("/ws"):
            url_path = url_path[:-3]
        parsed = parsed.with_path(url_path)

        is_secure = parsed.scheme in ("https", "wss")
        self._http_url = str(parsed.with_scheme("https" if is_secure else "http")).rstrip("/")
        self._ws_url = str(parsed.with_scheme("wss" if is_secure else "ws")).rstrip("/")

        self._session = session
        self._password = password
        self._token: str | None = None
        self._client_id = f"{CLIENT_ID_PREFIX}:{uuid.uuid4().hex[:8]}"

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._listen_task: asyncio.Task | None = None
        self._closed = False
        self._connected_event = asyncio.Event()
        self._pending_futures: dict[str, asyncio.Future[str]] = {}
        self._pending_deltas: dict[str, list[str]] = {}

    @property
    def http_url(self) -> str:
        """Return the HTTP/HTTPS base URL.
        返回 HTTP/HTTPS 基础地址。
        """
        return self._http_url

    def _build_ws_url(self) -> str:
        """Build the complete WebSocket URL with query parameters.
        构建携带客户端查询参数的完整 WebSocket URL。
        """
        query = {
            "clientId": self._client_id,
            "channelType": CHANNEL_TYPE,
            "sessionId": f"{CLIENT_ID_PREFIX}:main",
        }
        ws_url = f"{self._ws_url}/ws"
        return str(URL(ws_url).update_query(query))

    def _get_auth_headers(self) -> dict[str, str]:
        """Return authorization headers if a valid session token exists.
        如果有会话 Token，则返回对应的认证请求头。
        """
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def async_login(self) -> None:
        """Authenticate with Freya and acquire a session token.
        向 Freya 发起鉴权，换取会话 Token。如果服务端未开启鉴权，依然会返回一个可用 Token。
        """
        login_url = f"{self.http_url}/api/auth/login"
        payload = {}
        if self._password:
            payload["password"] = self._password
            
        try:
            async with self._session.post(login_url, json=payload) as resp:
                data = await resp.json()
                if resp.status == 200 and data.get("success"):
                    self._token = data.get("token")
                else:
                    err_msg = data.get("error", "Unknown auth error")
                    raise FreyaApiClientAuthenticationError(f"Login failed: {err_msg}")
        except aiohttp.ClientError as err:
            raise FreyaApiClientCommunicationError(f"Request to login failed: {err}") from err

    async def async_upload_file(self, file_path: str) -> dict[str, Any]:
        """Upload a local file to Freya via HTTP /ws/upload.
        通过 HTTP /ws/upload 将本地文件上传至 Freya 工作区缓存。
        """
        path_obj = Path(file_path)
        filename = path_obj.name
        upload_url = f"{self.http_url}/ws/upload"

        data = await asyncio.to_thread(path_obj.read_bytes)
        if self._password and not self._token:
            await self.async_login()

        headers = self._get_auth_headers()
        headers["Content-Type"] = "application/octet-stream"
        headers["X-File-Name"] = quote(filename)

        try:
            async with self._session.post(upload_url, data=data, headers=headers) as resp:
                if resp.status in (401, 403):
                    self._token = None
                    raise FreyaApiClientAuthenticationError("Token expired during upload")
                if resp.status != 200:
                    err_text = await resp.text()
                    raise FreyaApiClientCommunicationError(
                        f"Upload failed with status {resp.status}: {err_text}"
                    )
                json_res = await resp.json()
                return json_res.get("data", {})
        except aiohttp.ClientError as err:
            raise FreyaApiClientCommunicationError(
                f"Failed to upload file to Freya: {err}"
            ) from err

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
                if self._password and not self._token:
                    await self.async_login()

                ws_url = self._build_ws_url()
                async with self._session.ws_connect(
                    ws_url,
                    autoping=True,
                    headers=self._get_auth_headers(),
                ) as ws:
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

            except FreyaApiClientAuthenticationError as err:
                LOGGER.debug("Freya authentication error in connection loop: %s", err)
                self._token = None
                await asyncio.sleep(5)
            except aiohttp.WSServerHandshakeError as err:
                if err.status in (401, 403):
                    LOGGER.debug("Freya WebSocket handshake rejected (401/403). Resetting token.")
                    self._token = None
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
            if self._password:
                await self.async_login()
            ws_url = self._build_ws_url()
            async with asyncio.timeout(10):
                async with self._session.ws_connect(
                    ws_url,
                    autoping=True,
                    headers=self._get_auth_headers(),
                ) as ws:
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

