import asyncio
import json
import html
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import can
import cantools

from py_data_acq.io_handler.can_handle import init_can

class MCAPServer:
    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 6969,
        can_bus: can.Bus | None = None,
        can_db: cantools.database.Database | None = None,
        dbc_file: str | None = None,
        can_message_name: str | None = None,
        can_message_defaults: dict[str, Any] | None = None,
    ):
        self.host = host
        self.port = port
        self._external_can_bus = can_bus is not None
        self.can_bus = can_bus or init_can()
        self._dbc_file = dbc_file
        self.can_db = can_db or self._load_can_database(dbc_file)
        self.can_command_message = can_message_name
        self.can_command_defaults = can_message_defaults or {}
        self.can_status_message = (
            f"Ready to send CAN command '{self.can_command_message}'"
            if self.can_command_message
            else "Select a CAN message to send."
        )
        self.can_message_options_html = ""
        self._ensure_can_database()
        self.html_content = b"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CAN Control</title>
    <script>
        function sendCommand(command, params) {
        let url = '/' + command;
        if (params && params.toString().length > 0) {
            url += '?' + params.toString();
        }
        fetch(url, { method: 'POST' })
            .then(response => response.text())
            .then(data => {
                alert(data);
                setTimeout(updateStatus, 1000)
            })
            .catch((error) => {
                console.error('Error:', error);
                alert('Error sending command: ' + command);
            });
        }
        function updateSignalOverridesFromSelect() {
            const select = document.getElementById('canMessageSelect');
            const textarea = document.getElementById('canPayloadInput');
            if (!select || !textarea || select.selectedIndex < 0) {
                return;
            }
            const option = select.options[select.selectedIndex];
            if (!option) {
                return;
            }
            const template = option.getAttribute('data-signals');
            if (template) {
                try {
                    const parsed = JSON.parse(template);
                    textarea.value = JSON.stringify(parsed, null, 2);
                } catch (err) {
                    console.error('Failed to parse signal template', err);
                }
            }
        }
        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    const canStatus = document.getElementById('canStatus');
                    if (canStatus) {
                        canStatus.innerText = data.canStatusMessage;
                    }
                    const select = document.getElementById('canMessageSelect');
                    if (select && data.messageOptions) {
                        const currentValue = select.value;
                        select.innerHTML = data.messageOptions;
                        if (currentValue) {
                            select.value = currentValue;
                            if (select.value !== currentValue && data.currentMessage) {
                                select.value = data.currentMessage;
                            }
                        } else if (data.currentMessage) {
                            select.value = data.currentMessage;
                        }
                    }
                    updateSignalOverridesFromSelect();
                });
        }
        function sendCanCommand() {
            const select = document.getElementById('canMessageSelect');
            const valueInput = document.getElementById('canValueInput');
            const payloadInput = document.getElementById('canPayloadInput');
            const params = new URLSearchParams();
            if (select && select.value) {
                params.append('message', select.value);
            }
            if (valueInput && valueInput.value !== '') {
                params.append('value', valueInput.value);
            }
            if (payloadInput && payloadInput.value.trim().length > 0) {
                params.append('payload', payloadInput.value.trim());
            }
            sendCommand('send_can', params);
        }
        document.addEventListener('DOMContentLoaded', function() {
            updateStatus();
            const select = document.getElementById('canMessageSelect');
            if (select) {
                select.addEventListener('change', updateSignalOverridesFromSelect);
            }
            updateSignalOverridesFromSelect();
        }, false);
    </script>
</head>
<body>
    <h1>CAN Control Panel</h1>
    <div>
        <label for="canMessageSelect">CAN Message</label>
        <select id="canMessageSelect">
            {{can_options}}
        </select>
    </div>
    <div>
        <label for="canValueInput">Value</label>
        <input id="canValueInput" type="number" step="any" placeholder="Value to send" />
    </div>
    <div>
        <label for="canPayloadInput">Signal Overrides (JSON)</label>
        <textarea id="canPayloadInput" placeholder='{"signal_name": 42}' rows="4" cols="40"></textarea>
    </div>
    <button id="sendCanBtn" onclick="sendCanCommand()">Send CAN Command</button>
    <div id="canStatus">{{can_status}}</div>
</body>
</html>"""

    def __await__(self):
        async def closure():
            return self
        return closure().__await__()
    def __enter__(self):
        return self
    def __exit__(self, exc_, exc_type_, tb_):
        pass
    def __aenter__(self):
        return self
    async def __aexit__(self, exc_type: Any, exc_val: Any, traceback: Any):
        if not self._external_can_bus and self.can_bus is not None:
            try:
                self.can_bus.shutdown()
            except AttributeError:
                pass
    
    def _load_can_database(self, dbc_file: str | None):
        if not dbc_file:
            return None
        try:
            return cantools.db.load_file(dbc_file)
        except Exception as exc:
            self.can_status_message = f"Failed to load CAN database: {exc}"
            return None

    def _ensure_can_database(self) -> bool:
        if self.can_db is not None:
            if not self.can_message_options_html:
                self.can_message_options_html = self._build_can_options()
            return True
        self.can_db = self._load_can_database(self._dbc_file)
        if self.can_db is None:
            self.can_status_message = "CAN database unavailable."
            return False
        self.can_message_options_html = self._build_can_options()
        return True

    def _default_signal_values(self, message) -> dict[str, Any]:
        defaults: dict[str, Any] = {}
        for signal in message.signals:
            if signal.name in self.can_command_defaults:
                defaults[signal.name] = self.can_command_defaults[signal.name]
            elif signal.initial is not None:
                defaults[signal.name] = signal.initial
            else:
                defaults[signal.name] = 0
        return defaults

    @staticmethod
    def _get_single_query_value(query: dict[str, list[str]], key: str) -> str | None:
        values = query.get(key)
        if not values:
            return None
        return values[0]

    @staticmethod
    def _coerce_numeric(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value.strip())
        raise ValueError(f"Unsupported numeric type: {type(value).__name__}")

    def _parse_payload_overrides(
        self, raw_payload: str | None
    ) -> tuple[dict[str, Any] | None, str | None]:
        if raw_payload in (None, ""):
            return None, None
        try:
            parsed = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            return None, f"Invalid payload JSON: {exc}"
        if not isinstance(parsed, dict):
            return None, "Payload overrides must be a JSON object."

        overrides: dict[str, Any] = {}
        for key, value in parsed.items():
            try:
                overrides[key] = self._coerce_numeric(value)
            except (ValueError, TypeError) as exc:
                return None, f"Invalid value for '{key}': {exc}"
        return overrides, None

    def _build_can_options(self) -> str:
        if not self.can_db or not self.can_db.messages:
            return '<option value="">No CAN messages available</option>'
        options = []
        for message in self.can_db.messages:
            selected = (
                ' selected'
                if self.can_command_message
                and message.name == self.can_command_message
                else ''
            )
            label = f"{message.name} (0x{message.frame_id:X})"
            template = html.escape(
                json.dumps(self._default_signal_values(message)), quote=True
            )
            options.append(
                f'<option value="{message.name}" data-signals="{template}"{selected}>{label}</option>'
            )
        if not self.can_command_message:
            self.can_command_message = self.can_db.messages[0].name
            options[0] = options[0].replace('>', ' selected>', 1)
        return "".join(options)
    
    # Creates page from inline html and updates with CAN status/options
    async def serve_file(self):
        self._ensure_can_database()
        current_html_content = (
            self.html_content
            .replace(b'{{can_status}}', self.can_status_message.encode())
            .replace(b'{{can_options}}', self.can_message_options_html.encode())
        )
        header = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
        return header + current_html_content
        
    def _select_command_message(self, preferred_name: str | None = None):
        if not self._ensure_can_database():
            return None
        if self.can_db is None:
            return None
        target_name = preferred_name or self.can_command_message
        if target_name:
            try:
                return self.can_db.get_message_by_name(target_name)
            except KeyError:
                self.can_status_message = (
                    f"Message '{target_name}' not found in DBC."
                )
                return None
        if not self.can_db.messages:
            self.can_status_message = "CAN database has no messages."
            return None
        return self.can_db.messages[0]

    def _build_signal_payload(
        self,
        message,
        overrides: dict[str, Any] | None,
        fallback_value: float | None,
    ):
        payload = self._default_signal_values(message)
        overrides = overrides or {}
        for signal_name, value in overrides.items():
            payload[signal_name] = value
        if fallback_value is not None:
            for signal in message.signals:
                if signal.name not in overrides:
                    payload[signal.name] = fallback_value
                    break
        return payload

    def send_can_command(
        self,
        message_name: str | None = None,
        override_value: float | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> str:
        if self.can_bus is None:
            self.can_status_message = "CAN bus not available."
            return self.can_status_message

        message = self._select_command_message(message_name)
        if message is None:
            return self.can_status_message

        self.can_command_message = message.name
        self.can_message_options_html = self._build_can_options()
        payload_values = self._build_signal_payload(message, overrides, override_value)
        try:
            encoded = message.encode(payload_values, scaling=True)
        except Exception as exc:
            self.can_status_message = f"Failed to encode {message.name}: {exc}"
            return self.can_status_message

        can_message = can.Message(
            arbitration_id=message.frame_id,
            data=encoded,
            is_extended_id=message.is_extended_frame,
            is_fd=message.is_fd,
        )

        try:
            self.can_bus.send(can_message)
            timestamp = time.strftime("%H:%M:%S")
            self.can_status_message = (
                f"Sent CAN message '{message.name}' (0x{message.frame_id:X}) at {timestamp} "
                f"data=0x{encoded.hex().upper()}"
            )
        except can.CanError as exc:
            self.can_status_message = f"Failed to send CAN message: {exc}"
        return self.can_status_message

    def handle_command(self, command, query: dict[str, list[str]] | None = None):
        query = query or {}
        if command == '/send_can':
            message_name = self._get_single_query_value(query, 'message')
            raw_value = self._get_single_query_value(query, 'value')
            override_value = None
            if raw_value not in (None, ""):
                try:
                    override_value = float(raw_value)
                except ValueError:
                    self.can_status_message = f"Invalid CAN value '{raw_value}'"
                    return self.can_status_message
            raw_payload = self._get_single_query_value(query, 'payload')
            payload_overrides, error = self._parse_payload_overrides(raw_payload)
            if error:
                self.can_status_message = error
                return self.can_status_message
            return self.send_can_command(message_name, override_value, payload_overrides)
        else:
            return "Command not recognized."


    # Checks if client connected and updates them on different actions
    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"Connected with {addr}")
        
        data = await reader.read(4096)
        request = data.decode('utf-8', errors='ignore')
        request_line = request.splitlines()[0] if request else ""
        if not request_line:
            writer.close()
            await writer.wait_closed()
            return
        method, url, _ = request_line.split(' ', 2)
        parsed = urlparse(url)
        path = parsed.path
        query = parse_qs(parsed.query)

        if method == 'POST':
            response_text = self.handle_command(path, query)
            response = (f"HTTP/1.1 200 OK\r\n"
                        f"Content-Type: text/plain\r\n\r\n"
                        f"{response_text}").encode('utf-8')
        elif path == '/status':
            self._ensure_can_database()
            status_response = {
                "canStatusMessage": self.can_status_message,
                "messageOptions": self.can_message_options_html,
                "currentMessage": self.can_command_message,
            }
            response_bytes = json.dumps(status_response).encode('utf-8')
            response = (f"HTTP/1.1 200 OK\r\n"
                        f"Content-Type: application/json\r\n\r\n").encode('utf-8') + response_bytes
        else:
            response = await self.serve_file()

        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        
    async def start_server(self):
        url = f"http://{self.host}:{self.port}"
        print(f"CAN control server started on {url}")
        server = await asyncio.start_server(self.handle_client, self.host, self.port)

        async with server:
            await server.serve_forever()

    