from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from .hl7_parser import build_hl7_ack


MLLP_START_BLOCK = b"\x0b"
MLLP_END_BLOCK = b"\x1c\x0d"


MessageHandler = Callable[[str, str], Awaitable[dict[str, Any] | None]]


def extract_mllp_messages(buffer: bytes) -> tuple[list[bytes], bytes]:
    messages: list[bytes] = []
    cursor = buffer

    while True:
        start = cursor.find(MLLP_START_BLOCK)
        if start < 0:
            return messages, cursor

        end = cursor.find(MLLP_END_BLOCK, start + 1)
        if end < 0:
            return messages, cursor[start:]

        payload = cursor[start + 1 : end]
        messages.append(payload)
        cursor = cursor[end + len(MLLP_END_BLOCK) :]


class Hl7MllpListener:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        on_message: MessageHandler | None,
    ) -> None:
        self.host = host
        self.port = port
        self.on_message = on_message
        self._server: asyncio.AbstractServer | None = None

    @property
    def is_running(self) -> bool:
        return self._server is not None

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername")
        peer_label = f"{peer[0]}:{peer[1]}" if isinstance(peer, tuple) and len(peer) >= 2 else "unknown"
        buffer = b""

        try:
            while not reader.at_eof():
                chunk = await reader.read(4096)
                if not chunk:
                    break
                buffer += chunk
                messages, buffer = extract_mllp_messages(buffer)

                for payload in messages:
                    hl7_message = payload.decode("utf-8", errors="replace")
                    ack_code = "AA"
                    ack_text = "Message accepted"

                    if self.on_message:
                        try:
                            result = await self.on_message(hl7_message, peer_label)
                            if result and result.get("error"):
                                ack_code = "AE"
                                ack_text = str(result["error"])[:120]
                        except Exception as exc:  # noqa: BLE001
                            ack_code = "AE"
                            ack_text = f"Listener error: {exc}"[:120]

                    ack = build_hl7_ack(hl7_message, ack_code=ack_code, text=ack_text)
                    writer.write(MLLP_START_BLOCK + ack.encode("utf-8") + MLLP_END_BLOCK)
                    await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
