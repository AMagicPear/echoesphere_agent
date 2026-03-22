"""TCP server with a simple length-prefixed binary protocol.

Protocol
--------
Each message is encoded as:
  - 4 bytes (big-endian, signed int): total byte length of the payload
  - 1 byte: message type (0x00 = TEXT, 0x01 = IMAGE)
  - N bytes: payload data

All integers use network byte order (big-endian).
"""

import asyncio
import logging
import struct
from typing import Callable, Optional

logger = logging.getLogger("echoesphere.server")


class MessageType:
    TEXT = 0x00
    IMAGE = 0x01


class ClientConnection:
    """Holds state for a single connected client."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        client_id: str,
    ):
        self.reader = reader
        self.writer = writer
        self.client_id = client_id
        self._receive_task: Optional[asyncio.Task[None]] = None

    async def start(self, on_text: Callable[[str], None], on_image: Callable[[bytes], None]) -> asyncio.Task[None]:
        self._receive_task = asyncio.create_task(self._receive_loop(on_text, on_image))
        return self._receive_task

    async def _receive_loop(
        self,
        on_text: Callable[[str], None],
        on_image: Callable[[bytes], None],
    ) -> None:
        logger.debug("Receive loop started for %s", self.client_id)
        try:
            while True:
                length_data = await self.reader.readexactly(4)
                total_length = struct.unpack("!i", length_data)[0]
                data_with_type = await self.reader.readexactly(total_length)
                msg_type = data_with_type[0]
                payload = data_with_type[1:]

                if msg_type == MessageType.TEXT:
                    on_text(payload.decode("utf-8"))
                elif msg_type == MessageType.IMAGE:
                    on_image(payload)
                else:
                    logger.warning("Unknown message type: %s from %s", msg_type, self.client_id)
        except asyncio.IncompleteReadError:
            logger.info("Connection closed by peer: %s", self.client_id)
        except ConnectionResetError:
            logger.warning("Connection reset: %s", self.client_id)
        except Exception:
            logger.exception("Unexpected error in receive loop for %s", self.client_id)
        finally:
            self.writer.close()
            await self.writer.wait_closed()

    async def send_text(self, text: str) -> None:
        """Send a UTF-8 text message to this client."""
        data = text.encode("utf-8")
        total_length = 1 + len(data)
        self.writer.write(struct.pack("!i", total_length))
        self.writer.write(bytes([MessageType.TEXT]) + data)
        await self.writer.drain()

    async def send_image(self, image_bytes: bytes) -> None:
        """Send raw image bytes to this client."""
        total_length = 1 + len(image_bytes)
        self.writer.write(struct.pack("!i", total_length))
        self.writer.write(bytes([MessageType.IMAGE]) + image_bytes)
        await self.writer.drain()

    def cancel(self) -> None:
        if self._receive_task:
            self._receive_task.cancel()
            self._receive_task = None


class TcpServer:
    """Async TCP server that accepts multiple clients.

    Supports text and image messages with a length-prefixed framing protocol.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 65432,
        on_text: Optional[Callable[[str], None]] = None,
        on_image: Optional[Callable[[bytes], None]] = None,
    ):
        self.host = host
        self.port = port
        self._user_on_text = on_text or (lambda msg: None)
        self._user_on_image = on_image or (lambda img: None)
        self._server: Optional[asyncio.Server] = None
        self._clients: dict[str, ClientConnection] = {}

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        logger.info("Listening on %s:%s", self.host, self.port)

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        client_addr = writer.get_extra_info("peername")
        client_id = f"{client_addr[0]}:{client_addr[1]}"
        conn = ClientConnection(reader, writer, client_id)
        self._clients[client_id] = conn
        logger.info("Client connected: %s", client_id)

        try:
            receive_task = await conn.start(
                lambda msg: self._on_text(msg, client_id),
                lambda img: self._on_image(img, client_id),
            )
            await receive_task
        finally:
            conn.cancel()
            self._clients.pop(client_id, None)
            logger.info("Client disconnected: %s", client_id)

    def _on_text(self, msg: str, client_id: str) -> None:
        logger.info("Text from %s: %s", client_id, msg)
        self._user_on_text(msg)

    def _on_image(self, img: bytes, client_id: str) -> None:
        logger.info("Image from %s: %d bytes", client_id, len(img))
        self._user_on_image(img)

    async def send_to_all(self, text: str) -> None:
        """Broadcast a text message to all connected clients."""
        for conn in self._clients.values():
            try:
                await conn.send_text(text)
            except Exception as e:
                logger.error("Send to %s failed: %s", conn.client_id, e)

    async def send_image_to_all(self, image_bytes: bytes) -> None:
        """Broadcast an image to all connected clients."""
        for conn in self._clients.values():
            try:
                await conn.send_image(image_bytes)
            except Exception as e:
                logger.error("Send image to %s failed: %s", conn.client_id, e)

    async def send_to_client(self, client_id: str, text: str) -> bool:
        """Send a text message to a specific client. Returns True if sent."""
        conn = self._clients.get(client_id)
        if not conn:
            logger.warning("Client not found: %s", client_id)
            return False
        await conn.send_text(text)
        return True

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def close(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for conn in list(self._clients.values()):
            conn.cancel()
        self._clients.clear()


# ----------------------------------------------------------------------
# Standalone test (Python acts as server, use telnet/nc to connect)
# ----------------------------------------------------------------------
async def _test_main() -> None:
    logging.basicConfig(level=logging.INFO)
    server = TcpServer("0.0.0.0", 65432)
    await server.start()

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(_test_main())