import asyncio
import time
from pathlib import Path
from typing import Any

import foxglove
from foxglove import Channel, Context, Schema

from py_data_acq.common.common_types import QueueData

def _normalize_identifier(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum() or ch == "_")


class HTProtobufFoxgloveServer:
    """
    Minimal wrapper around the foxglove-sdk websocket server that understands our
    protobuf descriptor set and streams queue data to per-message channels.
    """

    def __init__(
        self,
        host: str,
        port: int,
        name: str,
        pb_bin_file_path: str,
        schema_names: list[str],
    ):
        self.host = host
        self.port = port
        self.name = name
        self.schema_path = Path(pb_bin_file_path)
        self.schema_names = schema_names

        self._context = Context()
        self._server: foxglove.WebSocketServer | None = None
        self._channels: dict[str, Channel] = {}
        self._descriptor_bytes = self.schema_path.read_bytes()

    async def __aenter__(self) -> "HTProtobufFoxgloveServer":
        # start_server is synchronous but lightweight, so call it directly.
        self._server = foxglove.start_server(
            name=self.name,
            host=self.host,
            port=self.port,
            context=self._context,
            supported_encodings=["protobuf"],
        )
        self._register_channels()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, traceback: Any) -> None:
        if self._server is not None:
            self._server.stop()
            self._server = None
        self._channels.clear()

    def _register_channels(self) -> None:
        for name in self.schema_names:
            schema = Schema(name=name, encoding="protobuf", data=self._descriptor_bytes)
            self._channels[name] = Channel(
                f"{name}_data",
                message_encoding="protobuf",
                schema=schema,
                context=self._context,
            )

    async def send_msgs_from_queue(self, queue: asyncio.Queue[QueueData]) -> None:
        try:
            data = await queue.get()
            if data is None:
                return

            channel = self._channels.get(data.name)
            if channel is None:
                raise KeyError(f"Channel not registered for schema '{data.name}'")

            channel.log(data.data, log_time=time.time_ns())
        except asyncio.CancelledError:
            raise
