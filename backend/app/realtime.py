import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect

from .config import Settings

logger = logging.getLogger(__name__)


async def proxy_qwen_realtime(client: WebSocket, settings: Settings) -> None:
    if not settings.qwen_configured:
        await client.accept()
        await client.send_json(
            {
                "type": "error",
                "error": {"message": "Qwen Realtime is not configured on the backend"},
            }
        )
        await client.close(code=1011)
        return

    upstream_url = (
        f"wss://{settings.dashscope_workspace_id}."
        f"{settings.dashscope_endpoint_host}/api-ws/v1/realtime"
        f"?model={settings.dashscope_model}"
    )
    await client.accept()
    try:
        async with connect(
            upstream_url,
            additional_headers={
                "Authorization": f"Bearer {settings.dashscope_api_key}",
                "User-Agent": "omni-cloud-backend/0.1",
            },
            open_timeout=10,
            ping_interval=20,
            ping_timeout=20,
            max_size=4 * 1024 * 1024,
        ) as upstream:
            client_to_upstream = asyncio.create_task(_relay_client(client, upstream))
            upstream_to_client = asyncio.create_task(_relay_upstream(upstream, client))
            done, pending = await asyncio.wait(
                {client_to_upstream, upstream_to_client},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                error = task.exception()
                if error and not isinstance(error, WebSocketDisconnect):
                    raise error
    except WebSocketDisconnect:
        return
    except Exception as error:
        logger.exception("Qwen Realtime proxy failed")
        try:
            await client.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "error": {"message": f"Realtime upstream failed: {error}"},
                    },
                    ensure_ascii=False,
                )
            )
            await client.close(code=1011)
        except Exception:
            pass


async def _relay_client(client: WebSocket, upstream) -> None:
    while True:
        message = await client.receive()
        message_type = message.get("type")
        if message_type == "websocket.disconnect":
            return
        if text := message.get("text"):
            await upstream.send(text)
        elif data := message.get("bytes"):
            await upstream.send(data)


async def _relay_upstream(upstream, client: WebSocket) -> None:
    async for message in upstream:
        if isinstance(message, bytes):
            await client.send_bytes(message)
        else:
            await client.send_text(message)
