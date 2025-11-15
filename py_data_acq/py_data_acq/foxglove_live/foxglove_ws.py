import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

import can
import foxglove
from foxglove import Channel, Context, Schema
from foxglove.websocket import (
    AnyNativeParameterValue,
    Capability,
    Client,
    Parameter,
    ServerListener,
)

from py_data_acq.common.common_types import QueueData
from py_data_acq.io_handler.can_handle import init_can

LOGGER = logging.getLogger(__name__)


def _normalize_identifier(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum() or ch == "_")


class _CANSignalPublisher:
    def __init__(
        self,
        can_db,
        bus: can.Bus | None = None,
    ):
        self._db = can_db
        self._external_bus = bus is not None
        self._bus = bus or init_can()
        self._message_lookup = {
            _normalize_identifier(message.name): message
            for message in self._db.messages
        }
        self._signal_lookup: dict[str, dict[str, str]] = {}
        self._message_state: dict[str, dict[str, Any]] = {}
        for message in self._db.messages:
            self._signal_lookup[message.name] = {
                _normalize_identifier(signal.name): signal.name
                for signal in message.signals
            }
            self._message_state[message.name] = {
                signal.name: signal.initial if signal.initial is not None else 0
                for signal in message.signals
            }

    def close(self) -> None:
        if not self._external_bus:
            try:
                self._bus.shutdown()
            except AttributeError:
                pass

    def available_targets(self) -> Iterable[tuple[str, Iterable[str]]]:
        for message in self._db.messages:
            yield message.name, (signal.name for signal in message.signals)

    def write_signal(self, message_name: str, signal_name: str, value: Any) -> None:
        message = self._resolve_message(message_name)
        if message is None:
            raise KeyError(f"Unknown CAN message '{message_name}'")

        resolved_signal = self._resolve_signal(message, signal_name)
        if resolved_signal is None:
            raise KeyError(
                f"Unknown signal '{signal_name}' for CAN message '{message.name}'"
            )

        state = self._message_state[message.name]
        state[resolved_signal] = value

        payload = message.encode(state, strict=False)
        can_msg = can.Message(
            arbitration_id=message.frame_id,
            data=payload,
            is_extended_id=message.is_extended_frame,
            is_fd=message.is_fd,
        )
        self._bus.send(can_msg)

    def _resolve_message(self, message_name: str):
        return self._message_lookup.get(_normalize_identifier(message_name))

    def _resolve_signal(self, message, signal_name: str) -> str | None:
        signal_map = self._signal_lookup.get(message.name, {})
        return signal_map.get(_normalize_identifier(signal_name))


class _ParameterManager(ServerListener):
    def __init__(
        self,
        initial_values: Mapping[
            str, Parameter | AnyNativeParameterValue
        ]
        | None = None,
        can_publisher: _CANSignalPublisher | None = None,
        parameter_signal_map: Mapping[str, tuple[str, str]] | None = None,
    ):
        self._parameters: dict[str, Parameter] = {}
        self._server: foxglove.WebSocketServer | None = None
        self._can_publisher = can_publisher
        self._parameter_signal_map: dict[str, tuple[str, str]] = {}
        if parameter_signal_map:
            for key, target in parameter_signal_map.items():
                self._parameter_signal_map[_normalize_identifier(key)] = target
        if self._can_publisher is not None:
            for message_name, signal_names in self._can_publisher.available_targets():
                for signal_name in signal_names:
                    key = _normalize_identifier(f"{message_name}.{signal_name}")
                    self._parameter_signal_map.setdefault(
                        key, (message_name, signal_name)
                    )
        if initial_values:
            for name, value in initial_values.items():
                self._parameters[name] = self._make_parameter(name, value)

    def attach_server(self, server: foxglove.WebSocketServer) -> None:
        self._server = server
        if not self._parameters:
            return
        try:
            self._publish(list(self._parameters.values()))
        except Exception as exc:
            LOGGER.warning("Failed to publish initial parameters: %s", exc)

    def set_local_parameter(
        self, name: str, value: Parameter | AnyNativeParameterValue
    ) -> None:
        param = self._make_parameter(name, value)
        self._parameters[name] = param
        self._publish([param])
        self._write_to_can(param)

    def get_parameter_value(
        self, name: str, default: Any | None = None
    ) -> Any | None:
        parameter = self._parameters.get(name)
        return parameter.get_value() if parameter else default

    def all_parameters(self) -> list[Parameter]:
        return list(self._parameters.values())

    def on_get_parameters(  # type: ignore[override]
        self,
        client: Client,
        param_names: list[str],
        request_id: str | None = None,
    ) -> list[Parameter]:
        if not param_names:
            return self.all_parameters()
        return [
            self._parameters[name]
            for name in param_names
            if name in self._parameters
        ]

    def on_set_parameters(  # type: ignore[override]
        self,
        client: Client,
        parameters: list[Parameter],
        request_id: str | None = None,
    ) -> list[Parameter]:
        for parameter in parameters:
            updated = self._update_from_parameter(parameter)
            if updated is None:
                self._parameters.pop(parameter.name, None)
            else:
                self._parameters[parameter.name] = updated
                self._write_to_can(updated)
        return self.all_parameters()

    def on_parameters_subscribe(  # type: ignore[override]
        self, param_names: list[str]
    ) -> None:
        self._publish(
            self.all_parameters() if not param_names else [
                self._parameters[name]
                for name in param_names
                if name in self._parameters
            ]
        )

    def _publish(self, params: Iterable[Parameter]) -> None:
        if self._server is None:
            return
        param_list = list(params)
        if param_list:
            self._server.publish_parameter_values(param_list)

    @staticmethod
    def _make_parameter(
        name: str, value: Parameter | AnyNativeParameterValue
    ) -> Parameter:
        if isinstance(value, Parameter):
            return Parameter(
                name=name,
                value=value.get_value(),
                type=value.type,
            )
        return Parameter(name=name, value=value)

    @staticmethod
    def _update_from_parameter(parameter: Parameter) -> Parameter | None:
        native_value = parameter.get_value()
        if native_value is None:
            return None
        return Parameter(
            name=parameter.name,
            value=native_value,
            type=parameter.type,
        )

    def _write_to_can(self, parameter: Parameter) -> None:
        if self._can_publisher is None:
            return

        native_value = parameter.get_value()
        if native_value is None:
            return

        target = self._resolve_can_target(parameter.name)
        if target is None:
            return

        message_name, signal_name = target
        try:
            self._can_publisher.write_signal(message_name, signal_name, native_value)
        except Exception as exc:
            LOGGER.warning(
                "Failed to write parameter '%s' to CAN (%s.%s): %s",
                parameter.name,
                message_name,
                signal_name,
                exc,
            )

    def _resolve_can_target(self, parameter_name: str) -> tuple[str, str] | None:
        normalized = _normalize_identifier(parameter_name)
        if normalized in self._parameter_signal_map:
            return self._parameter_signal_map[normalized]

        for separator in (".", "/", ":"):
            if separator in parameter_name:
                message_name, signal_name = parameter_name.split(separator, 1)
                key = _normalize_identifier(f"{message_name}.{signal_name}")
                if key in self._parameter_signal_map:
                    return self._parameter_signal_map[key]
        return None

    def add_parameter_mapping(
        self, parameter_name: str, message_name: str, signal_name: str
    ) -> None:
        self._parameter_signal_map[_normalize_identifier(parameter_name)] = (
            message_name,
            signal_name,
        )


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
        initial_parameters: Mapping[
            str, Parameter | AnyNativeParameterValue
        ]
        | None = None,
        can_db=None,
        can_bus: can.Bus | None = None,
        parameter_signal_map: Mapping[str, tuple[str, str]] | None = None,
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
        self._can_publisher = (
            _CANSignalPublisher(can_db, can_bus) if can_db is not None else None
        )
        self._parameter_manager = _ParameterManager(
            initial_parameters,
            can_publisher=self._can_publisher,
            parameter_signal_map=parameter_signal_map,
        )

    async def __aenter__(self) -> "HTProtobufFoxgloveServer":
        # start_server is synchronous but lightweight, so call it directly.
        self._server = foxglove.start_server(
            name=self.name,
            host=self.host,
            port=self.port,
            context=self._context,
            supported_encodings=["protobuf"],
            capabilities=[Capability.Parameters],
            server_listener=self._parameter_manager,
        )
        self._register_channels()
        self._parameter_manager.attach_server(self._server)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, traceback: Any) -> None:
        if self._server is not None:
            self._server.stop()
            self._server = None
        self._channels.clear()
        if self._can_publisher is not None:
            self._can_publisher.close()

    def _register_channels(self) -> None:
        for name in self.schema_names:
            schema = Schema(name=name, encoding="protobuf", data=self._descriptor_bytes)
            self._channels[name] = Channel(
                f"{name}_data",
                message_encoding="protobuf",
                schema=schema,
                context=self._context,
            )

    def set_parameter(
        self, name: str, value: Parameter | AnyNativeParameterValue
    ) -> None:
        self._parameter_manager.set_local_parameter(name, value)

    def get_parameter(self, name: str, default: Any | None = None) -> Any | None:
        return self._parameter_manager.get_parameter_value(name, default)

    def map_parameter_to_can_signal(
        self, parameter_name: str, message_name: str, signal_name: str
    ) -> None:
        self._parameter_manager.add_parameter_mapping(
            parameter_name, message_name, signal_name
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
            pass
