"""Hardware-in-the-loop adapter layer.

The project can run in software-only mode by default. If no real hardware
adapter is available, the interface falls back to an in-memory virtual backend
that safely queues outbound payloads and can optionally loop them back for
development and testing.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import importlib
import time
from typing import Any, Deque, Dict, Optional


@dataclass
class HILMessage:
    timestamp: float
    payload: bytes
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HILState:
    tool: str
    backend: str = 'disconnected'
    connected: bool = False
    fallback_used: bool = False
    last_error: Optional[str] = None
    tx_count: int = 0
    rx_count: int = 0
    last_tx: Optional[bytes] = None
    last_rx: Optional[bytes] = None


class BaseHILBackend:
    backend_name = 'base'

    def __init__(self, tool: str, **kwargs: Any):
        self.tool = tool
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def send(self, payload: bytes) -> None:
        raise NotImplementedError

    def receive(self, timeout: float = 0.0) -> Optional[bytes]:
        raise NotImplementedError

    def status(self) -> Dict[str, Any]:
        return {'backend': self.backend_name, 'connected': self.connected}


class VirtualHILBackend(BaseHILBackend):
    backend_name = 'virtual'

    def __init__(self, tool: str = 'virtual', loopback: bool = True):
        super().__init__(tool)
        self.loopback = loopback
        self._tx_log: Deque[HILMessage] = deque()
        self._rx_queue: Deque[bytes] = deque()

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def send(self, payload: bytes) -> None:
        if not self.connected:
            raise RuntimeError('HIL backend is not connected')
        payload = bytes(payload)
        self._tx_log.append(HILMessage(timestamp=time.time(), payload=payload))
        if self.loopback:
            self._rx_queue.append(payload)

    def receive(self, timeout: float = 0.0) -> Optional[bytes]:
        if not self.connected:
            return None
        if self._rx_queue:
            return self._rx_queue.popleft()
        return None

    def inject_receive(self, payload: bytes) -> None:
        self._rx_queue.append(bytes(payload))

    def status(self) -> Dict[str, Any]:
        return {
            'backend': self.backend_name,
            'connected': self.connected,
            'tx_queue': len(self._tx_log),
            'rx_queue': len(self._rx_queue),
            'loopback': self.loopback,
        }


class ExternalHardwareBackend(BaseHILBackend):
    backend_name = 'external'

    def __init__(self, tool: str, module_name: Optional[str] = None):
        super().__init__(tool)
        self.module_name = module_name or tool
        self._module = None

    def connect(self) -> None:
        try:
            self._module = importlib.import_module(self.module_name)
        except Exception as exc:
            raise RuntimeError(f'No HIL API available for {self.tool}: {exc}') from exc
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def send(self, payload: bytes) -> None:
        raise RuntimeError(f'Hardware backend {self.module_name} is not implemented yet')

    def receive(self, timeout: float = 0.0) -> Optional[bytes]:
        raise RuntimeError(f'Hardware backend {self.module_name} is not implemented yet')


class HILInterface:
    """Stable HIL adapter with a safe software fallback."""

    SUPPORTED_TOOLS = {'virtual', 'dspace', 'ni', 'vector', 'can'}

    def __init__(self, tool: str = 'virtual', *, allow_fallback: bool = True, loopback: bool = True, backend: BaseHILBackend | None = None):
        self.tool = (tool or 'virtual').lower()
        self.allow_fallback = allow_fallback
        self._loopback = loopback
        self._backend = backend or self._create_backend(self.tool)
        self._state = HILState(tool=self.tool, backend=self._backend.backend_name)

    def _create_backend(self, tool: str) -> BaseHILBackend:
        if tool == 'virtual':
            return VirtualHILBackend(tool=tool, loopback=self._loopback)
        if tool in self.SUPPORTED_TOOLS:
            return ExternalHardwareBackend(tool=tool)
        return VirtualHILBackend(tool=tool, loopback=self._loopback)

    @staticmethod
    def _normalize_payload(data: Any) -> bytes:
        if data is None:
            return b''
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
        if isinstance(data, memoryview):
            return data.tobytes()
        if isinstance(data, str):
            text = data.strip().replace('0x', '').replace(',', ' ')
            if not text:
                return b''
            return bytes(int(chunk, 16) for chunk in text.split())
        if isinstance(data, (list, tuple)):
            return bytes(data)
        return bytes(data)

    def connect(self) -> bool:
        self._state.last_error = None
        try:
            self._backend.connect()
            self._state.connected = True
            self._state.backend = self._backend.backend_name
            self._state.fallback_used = isinstance(self._backend, VirtualHILBackend) and self.tool != 'virtual'
            return True
        except Exception as exc:
            self._state.last_error = str(exc)
            if not self.allow_fallback:
                self._state.connected = False
                raise

            self._backend = VirtualHILBackend(tool=self.tool, loopback=self._loopback)
            self._backend.connect()
            self._state.connected = True
            self._state.backend = self._backend.backend_name
            self._state.fallback_used = True
            self._state.last_error = str(exc)
            return True

    def disconnect(self) -> None:
        try:
            self._backend.disconnect()
        finally:
            self._state.connected = False

    def is_connected(self) -> bool:
        return self._state.connected and self._backend.connected

    def send_to_hil(self, data: Any) -> bool:
        if not self.is_connected():
            self._state.last_error = 'HIL is not connected'
            return False
        try:
            payload = self._normalize_payload(data)
            self._backend.send(payload)
            self._state.tx_count += 1
            self._state.last_tx = payload
            return True
        except Exception as exc:
            self._state.last_error = str(exc)
            return False

    def receive_from_hil(self, timeout: float = 0.0) -> Optional[bytes]:
        if not self.is_connected():
            self._state.last_error = 'HIL is not connected'
            return None
        try:
            payload = self._backend.receive(timeout=timeout)
            if payload is None:
                return None
            self._state.rx_count += 1
            self._state.last_rx = payload
            return payload
        except Exception as exc:
            self._state.last_error = str(exc)
            return None

    def status(self) -> Dict[str, Any]:
        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        state = {
            'tool': self._state.tool,
            'backend': self._state.backend,
            'connected': self._state.connected,
            'fallback_used': self._state.fallback_used,
            'last_error': self._state.last_error,
            'tx_count': self._state.tx_count,
            'rx_count': self._state.rx_count,
            'last_tx': self._state.last_tx,
            'last_rx': self._state.last_rx,
        }
        state.update(self._backend.status())
        return state

    def get_status(self) -> Dict[str, Any]:
        return self.get_state()


# Backward-compatible class name used by existing code.
class HIL(HILInterface):
    pass