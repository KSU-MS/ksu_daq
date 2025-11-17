import asyncio
import json
import html
import os
import time
from typing import Any, Iterable
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
        allowed_messages: Iterable[str] | str | None = None,
    ):
        self.host = host
        self.port = port
        self._external_can_bus = can_bus is not None
        self.can_bus = can_bus or init_can()
        self._dbc_file = dbc_file
        self.can_db = can_db or self._load_can_database(dbc_file)
        self.can_command_message = can_message_name
        self.can_command_defaults = can_message_defaults or {}
        env_allowed_messages = (
            None if allowed_messages is not None else os.getenv("CAN_ALLOWED_MESSAGES")
        )
        raw_allowed_messages = (
            allowed_messages if allowed_messages is not None else env_allowed_messages
        )
        self.allowed_message_names = self._normalize_allowed_messages(raw_allowed_messages)
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
    <style>
        :root {
            font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: #0f172a;
        }
        body {
            margin: 0;
            min-height: 100vh;
            background: linear-gradient(0deg, #ffc629 0%, rgba(0, 0, 0, 0.9) 35%, #000000 100%);
            color: #e2e8f0;
        }
        * {
            box-sizing: border-box;
        }
        .page {
            max-width: 980px;
            margin: 0 auto;
            padding: 2.5rem clamp(1.5rem, 4vw, 3rem) 3.5rem;
        }
        .hero {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid rgba(148, 163, 184, 0.2);
        }
        .hero h1 {
            margin: 0.4rem 0 0.25rem;
            font-size: clamp(1.75rem, 4vw, 2.4rem);
            color: #f8fafc;
        }
        .hero p {
            margin: 0;
            color: #94a3b8;
        }
        .eyebrow {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: #60a5fa;
        }
        .ghost-btn {
            border: 1px solid rgba(148, 163, 184, 0.6);
            background: transparent;
            color: #e2e8f0;
            padding: 0.65rem 1rem;
            border-radius: 999px;
            font-weight: 600;
            cursor: pointer;
            transition: all 160ms ease;
        }
        .ghost-btn:hover {
            border-color: #3b82f6;
            color: #3b82f6;
        }
        .content-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-top: 2rem;
        }
        .card {
            background: rgba(2, 6, 23, 0.88);
            border: 1px solid rgba(51, 65, 85, 0.9);
            border-radius: 18px;
            padding: 1.75rem;
            box-shadow: 0 25px 60px rgba(2, 6, 23, 0.45);
            backdrop-filter: blur(10px);
        }
        .card h2 {
            margin-top: 0;
            color: #f8fafc;
        }
        .form-grid {
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
            margin-top: 1rem;
        }
        label {
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: #94a3b8;
            margin-bottom: 0.5rem;
            display: block;
        }
        select,
        input,
        textarea {
            width: 100%;
            padding: 0.8rem 0.9rem;
            border-radius: 12px;
            border: 1px solid rgba(148, 163, 184, 0.4);
            background: rgba(15, 23, 42, 0.55);
            color: #e2e8f0;
            font-size: 1rem;
        }
        select option[hidden] {
            display: none;
        }
        .select-wrapper {
            display: flex;
            flex-direction: column;
            gap: 0.65rem;
        }
        .filter-input-row {
            display: flex;
            gap: 0.5rem;
            align-items: center;
        }
        .filter-input-row input {
            flex: 1;
        }
        .ghost-btn--compact {
            padding: 0.45rem 0.85rem;
            font-size: 0.85rem;
            border-radius: 10px;
        }
        .input-hint {
            font-size: 0.8rem;
            color: #94a3b8;
            margin: 0;
        }
        .input-hint--warning {
            color: #fca5a5;
        }
        textarea {
            min-height: 8rem;
            resize: vertical;
            font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
        }
        .primary-btn {
            width: fit-content;
            border: none;
            border-radius: 12px;
            padding: 0.85rem 1.75rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            color: #0f0f0f;
            background: linear-gradient(135deg, #ffc629, #d49b00);
            box-shadow: 0 8px 18px rgba(255, 198, 41, 0.2);
            transition: transform 160ms ease, box-shadow 160ms ease;
        }
        .primary-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 12px 26px rgba(255, 198, 41, 0.28);
        }
        .status-pill {
            display: inline-flex;
            padding: 0.75rem 1rem;
            border-radius: 14px;
            background: rgba(34, 197, 94, 0.18);
            border: 1px solid rgba(34, 197, 94, 0.4);
            color: #86efac;
            font-weight: 600;
            min-height: 3rem;
            align-items: center;
        }
        .helper-text {
            margin-top: 1rem;
            font-size: 0.9rem;
            color: #94a3b8;
            line-height: 1.4;
        }
        .toast {
            position: fixed;
            right: 1.5rem;
            bottom: 1.5rem;
            min-width: 280px;
            padding: 0.9rem 1rem;
            border-radius: 14px;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid rgba(148, 163, 184, 0.3);
            box-shadow: 0 18px 45px rgba(2, 6, 23, 0.55);
            color: #e2e8f0;
            font-weight: 500;
            transform: translateY(120%);
            opacity: 0;
            pointer-events: none;
            transition: transform 220ms ease, opacity 220ms ease;
        }
        .toast--visible {
            transform: translateY(0);
            opacity: 1;
            pointer-events: auto;
        }
        .toast--success {
            border-color: rgba(34, 197, 94, 0.5);
            color: #bbf7d0;
        }
        .toast--error {
            border-color: rgba(239, 68, 68, 0.5);
            color: #fecaca;
        }
        .toast--info {
            border-color: rgba(14, 165, 233, 0.5);
            color: #bae6fd;
        }
        .toast-close {
            background: transparent;
            border: none;
            color: inherit;
            font-size: 1.25rem;
            cursor: pointer;
            padding: 0;
            margin-left: auto;
        }
    </style>
    <script>
        let toastTimeout;
        function showToast(message, variant = 'info', duration = 3000) {
            const toast = document.getElementById('toast');
            const toastMessage = document.getElementById('toastMessage');
            if (!toast || !toastMessage) {
                return;
            }
            toast.classList.remove('toast--success', 'toast--error', 'toast--info', 'toast--visible');
            toastMessage.innerText = message;
            toast.classList.add(`toast--${variant}`, 'toast--visible');
            clearTimeout(toastTimeout);
            toastTimeout = setTimeout(() => hideToast(), duration);
        }
        function hideToast() {
            const toast = document.getElementById('toast');
            if (toast) {
                toast.classList.remove('toast--visible');
            }
        }
        function parseSignalTerms(value) {
            if (!value) {
                return [];
            }
            return value
                .split(/[,\\n]/)
                .map((term) => term.trim().toLowerCase())
                .filter(Boolean);
        }
        function optionMatchesSearch(option, terms) {
            if (!terms.length) {
                return true;
            }
            const signalNames = (option.dataset.signalNames || '').toLowerCase();
            const label = (option.textContent || '').toLowerCase();
            return terms.every((term) => signalNames.includes(term) || label.includes(term));
        }
        function applySignalSearch(options = {}) {
            const { preserveSelection = false } = options;
            const select = document.getElementById('canMessageSelect');
            const filterInput = document.getElementById('canSignalSearch');
            const noMatchesEl = document.getElementById('canMessageNoMatches');
            if (!select) {
                return;
            }
            const initialValue = select.value;
            const terms = parseSignalTerms(filterInput ? filterInput.value : '');
            let firstVisibleValue = null;
            const optionList = Array.from(select.options);
            optionList.forEach((option) => {
                const matches = optionMatchesSearch(option, terms);
                option.hidden = !matches;
                option.disabled = !matches;
                if (matches && firstVisibleValue === null) {
                    firstVisibleValue = option.value;
                }
            });
            let selectionChanged = false;
            if (preserveSelection) {
                const currentOption = select.querySelector(`option[value="${select.value}"]`);
                if (!currentOption || currentOption.hidden) {
                    select.value = firstVisibleValue ?? '';
                    selectionChanged = select.value !== initialValue;
                }
            } else {
                select.value = firstVisibleValue ?? '';
                selectionChanged = select.value !== initialValue;
            }
            if (selectionChanged) {
                updateSignalOverridesFromSelect(true);
            }
            if (noMatchesEl) {
                noMatchesEl.hidden = Boolean(firstVisibleValue);
            }
            return firstVisibleValue;
        }
        function clearSignalSearch() {
            const filterInput = document.getElementById('canSignalSearch');
            if (filterInput) {
                filterInput.value = '';
                applySignalSearch();
                filterInput.focus();
            }
        }
        function sendCommand(command, params) {
            let url = '/' + command;
            if (params && params.toString().length > 0) {
                url += '?' + params.toString();
            }
            fetch(url, { method: 'POST' })
                .then(response => response.text())
                .then(data => {
                    showToast(data, 'success');
                    setTimeout(updateStatus, 750);
                })
                .catch((error) => {
                    console.error('Error:', error);
                    showToast('Error sending command: ' + command, 'error', 4500);
                });
        }
        function updateSignalOverridesFromSelect(force = false) {
            const select = document.getElementById('canMessageSelect');
            const textarea = document.getElementById('canPayloadInput');
            if (!select || !textarea || select.selectedIndex < 0) {
                return;
            }
            if (!force && textarea.dataset.dirty === 'true') {
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
                    textarea.dataset.dirty = 'false';
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
                        const scrollTop = select.scrollTop;
                        select.innerHTML = data.messageOptions;
                        if (currentValue) {
                            select.value = currentValue;
                            if (select.value !== currentValue && data.currentMessage) {
                                select.value = data.currentMessage;
                            }
                        } else if (data.currentMessage) {
                            select.value = data.currentMessage;
                        }
                        select.scrollTop = scrollTop;
                        applySignalSearch({ preserveSelection: true });
                    }
                    const payloadInput = document.getElementById('canPayloadInput');
                    if (!payloadInput || payloadInput.dataset.dirty !== 'true') {
                        updateSignalOverridesFromSelect();
                    }
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
                select.addEventListener('change', () => updateSignalOverridesFromSelect(true));
            }
            const signalSearch = document.getElementById('canSignalSearch');
            if (signalSearch) {
                signalSearch.addEventListener('input', () => applySignalSearch());
                signalSearch.addEventListener('keydown', (event) => {
                    if (event.key === 'Escape') {
                        event.preventDefault();
                        clearSignalSearch();
                    }
                });
            }
            const clearSearchBtn = document.getElementById('clearSignalSearch');
            if (clearSearchBtn) {
                clearSearchBtn.addEventListener('click', clearSignalSearch);
            }
            const payloadInput = document.getElementById('canPayloadInput');
            if (payloadInput) {
                payloadInput.dataset.dirty = payloadInput.dataset.dirty || 'false';
                payloadInput.addEventListener('input', function() {
                    this.dataset.dirty = 'true';
                });
            }
            const form = document.getElementById('canForm');
            if (form) {
                form.addEventListener('submit', function(event) {
                    event.preventDefault();
                    sendCanCommand();
                });
            }
            const refreshBtn = document.getElementById('refreshStatusBtn');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', updateStatus);
            }
            const toastClose = document.getElementById('toastClose');
            if (toastClose) {
                toastClose.addEventListener('click', hideToast);
            }
            applySignalSearch({ preserveSelection: true });
            updateSignalOverridesFromSelect(true);
            setInterval(updateStatus, 8000);
        }, false);
    </script>
</head>
<body>
    <div class="page">
        <header class="hero">
            <div>
                <h1>CAN Control Panel</h1>
                <p>Craft CAN payloads, apply signal overrides, and send live commands.</p>
            </div>
            <button id="refreshStatusBtn" type="button" class="ghost-btn">Refresh</button>
        </header>
        <main class="content-grid">
            <section class="card form-card">
                <h2>Command Builder</h2>
                <form id="canForm" class="form-grid">
                    <div class="select-wrapper">
                        <label for="canMessageSelect">CAN Message</label>
                        <div class="filter-input-row">
                            <input id="canSignalSearch" type="text" placeholder="Type signal names (comma-separated) to filter" autocomplete="off" />
                            <button id="clearSignalSearch" type="button" class="ghost-btn ghost-btn--compact">Clear</button>
                        </div>
                        <select id="canMessageSelect">
                            {{can_options}}
                        </select>
                        <p id="canMessageNoMatches" class="input-hint input-hint--warning" hidden>No CAN messages match the current signal filter.</p>
                        <p class="input-hint">Type a signal name or comma-separated list to narrow the dropdown. Matching messages remain selectable below.</p>
                    </div>
                    <div>
                        <label for="canValueInput">Fallback Value</label>
                        <input id="canValueInput" type="number" step="any" placeholder="Value applied to the first signal" />
                    </div>
                    <div>
                        <label for="canPayloadInput">Signal Overrides (JSON)</label>
                        <textarea id="canPayloadInput" placeholder='{"signal_name": 42}'></textarea>
                    </div>
                    <div>
                        <button id="sendCanBtn" class="primary-btn" type="submit">Send CAN Command</button>
                    </div>
                </form>
            </section>
            <section class="card status-card">
                <h2>Live Status</h2>
                <div id="canStatus" class="status-pill">{{can_status}}</div>
                <div class="helper-text">
                    <p>Status updates automatically every few seconds. Use the refresh button for an instant update or adjust message payloads on the left.</p>
                </div>
            </section>
        </main>
    </div>
    <div id="toast" class="toast toast--info">
        <span id="toastMessage">Ready.</span>
        <button id="toastClose" class="toast-close" type="button" aria-label="Dismiss notification">&times;</button>
    </div>
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

    @staticmethod
    def _normalize_allowed_messages(
        raw_allowed: Iterable[str] | str | None,
    ) -> set[str]:
        if raw_allowed in (None, "", []):
            return set()
        tokens: list[str] = []
        if isinstance(raw_allowed, str):
            normalized = raw_allowed.replace("\n", ",").replace(";", ",")
            tokens = [part.strip() for part in normalized.split(",")]
        elif isinstance(raw_allowed, Iterable):
            for entry in raw_allowed:
                if entry is None:
                    continue
                tokens.append(str(entry).strip())
        else:
            return set()
        return {token.lower() for token in tokens if token}

    def _message_is_allowed(self, message) -> bool:
        if not self.allowed_message_names:
            return True
        return message.name.lower() in self.allowed_message_names

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
            self.can_status_message = "CAN database has no messages."
            self.can_command_message = None
            return '<option value="">No CAN messages available</option>'

        allowed_messages = [
            message
            for message in self.can_db.messages
            if self._message_is_allowed(message)
        ]

        if not allowed_messages:
            self.can_command_message = None
            placeholder = (
                "No CAN messages match the allowed message filter"
                if self.allowed_message_names
                else "No CAN messages available"
            )
            self.can_status_message = (
                "No CAN messages match the allowed message filter."
                if self.allowed_message_names
                else "CAN database has no messages."
            )
            return f'<option value="">{html.escape(placeholder)}</option>'

        allowed_names = {message.name for message in allowed_messages}
        preferred_selection = (
            self.can_command_message
            if self.can_command_message in allowed_names
            else None
        )
        if preferred_selection is None:
            preferred_selection = allowed_messages[0].name
        self.can_command_message = preferred_selection

        options = []
        for message in allowed_messages:
            selected = ' selected' if message.name == preferred_selection else ''
            label = f"{message.name} (0x{message.frame_id:X})"
            template = html.escape(
                json.dumps(self._default_signal_values(message)),
                quote=True,
            )
            signal_names_attr = html.escape(
                ",".join(
                    signal.name.lower()
                    for signal in getattr(message, 'signals', [])
                ),
                quote=True,
            )
            options.append(
                f'<option value="{message.name}" data-signals="{template}" '
                f'data-signal-names="{signal_names_attr}"{selected}>{label}</option>'
            )
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
                message = self.can_db.get_message_by_name(target_name)
            except KeyError:
                self.can_status_message = (
                    f"Message '{target_name}' not found in DBC."
                )
                return None
            if not self._message_is_allowed(message):
                self.can_status_message = (
                    f"Message '{target_name}' is blocked by the current message filter."
                )
                return None
            return message
        allowed_messages = [
            message
            for message in self.can_db.messages
            if self._message_is_allowed(message)
        ]
        if not allowed_messages:
            self.can_status_message = (
                "No CAN messages match the allowed message filter."
                if self.allowed_message_names
                else "CAN database has no messages."
            )
            return None
        return allowed_messages[0]

    def _build_signal_payload(
        self,
        message,
        overrides: dict[str, Any] | None,
        fallback_value: float | None,
    ):
        payload = {}
        overrides = overrides or {}
        fallback_consumed = False
        for signal in message.signals:
            if signal.name in overrides:
                payload[signal.name] = overrides[signal.name]
            elif fallback_value is not None and not fallback_consumed:
                payload[signal.name] = fallback_value
                fallback_consumed = True
            elif signal.name in self.can_command_defaults:
                payload[signal.name] = self.can_command_defaults[signal.name]
            elif signal.initial is not None:
                payload[signal.name] = signal.initial
            else:
                payload[signal.name] = 0
        return payload

    def _default_signal_values(self, message) -> dict[str, float]:
        """
        Build the default signal template used in the UI dropdown.

        Preference order:
            1. Explicit can_command_defaults passed to the server.
            2. Signal initial value defined in the DBC.
            3. Signal minimum (if defined) or 0 as the final fallback.
        """
        template: dict[str, float] = {}
        for signal in getattr(message, 'signals', []):
            if signal.name in self.can_command_defaults:
                template[signal.name] = float(self.can_command_defaults[signal.name])
            elif signal.initial is not None:
                template[signal.name] = float(signal.initial)
            elif signal.minimum is not None:
                template[signal.name] = float(signal.minimum)
            else:
                template[signal.name] = 0.0
        return template

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

    