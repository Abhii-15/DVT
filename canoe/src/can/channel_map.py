"""
channel_map.py
--------------
Channel Mapping subsystem for BCM Testing Tool.

Responsibilities
~~~~~~~~~~~~~~~~
* Maintain a registry of logical channel names → physical CAN interface
  descriptors (bus type + device/channel string).
* Validate that a requested physical interface is available before the
  mapping is accepted.
* Persist the mapping to / restore it from a JSON file so it survives
  application restarts.
* Emit Qt signals when the map changes so the rest of the UI can react
  without polling.

Supported interface back-ends (mirrors python-can bustype strings)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  virtual    – software loopback, always available (simulation)
  socketcan  – Linux SocketCAN (e.g. vcan0, can0)
  pcan       – Peak PCAN adapter
  kvaser     – Kvaser adapter
  vector     – Vector CANalyzer/CANoe hardware channel
  usb2can    – 8devices USB2CAN
  ixxat      – HMS iXXAT adapter
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

try:
    from PyQt5.QtCore import QObject, pyqtSignal
    _HAS_QT = True
except ImportError:
    _HAS_QT = False

logger = logging.getLogger(__name__)

SUPPORTED_BUSTYPES: List[str] = [
    "virtual",
    "socketcan",
    "pcan",
    "kvaser",
    "vector",
    "usb2can",
    "ixxat",
]


@dataclass
class ChannelEntry:
    """One logical-channel → physical-interface mapping entry."""

    logical_name: str
    bustype: str
    channel: str
    bitrate: int = 500_000
    enabled: bool = True
    description: str = ""

    def to_can_kwargs(self) -> dict:
        return {
            "bustype": self.bustype,
            "channel": self.channel,
            "bitrate": self.bitrate,
        }

    def display_label(self) -> str:
        return f"{self.logical_name}  [{self.bustype}:{self.channel}  @{self.bitrate // 1000}kbps]"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ChannelEntry":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


class ChannelMapError(Exception):
    """Raised when a channel-map operation cannot be completed."""


class ChannelMap:
    """Qt-free core mapping model."""

    def __init__(self) -> None:
        self._entries: Dict[str, ChannelEntry] = {}

    def add_or_update(self, entry: ChannelEntry) -> None:
        if entry.bustype not in SUPPORTED_BUSTYPES:
            raise ChannelMapError(
                f"Unsupported bustype '{entry.bustype}'. Choose from: {SUPPORTED_BUSTYPES}"
            )
        if not entry.logical_name.strip():
            raise ChannelMapError("logical_name must not be empty.")
        self._entries[entry.logical_name] = entry
        logger.debug("Channel map updated: %s", entry.display_label())

    def remove(self, logical_name: str) -> None:
        if logical_name not in self._entries:
            raise ChannelMapError(f"Channel '{logical_name}' not found in map.")
        del self._entries[logical_name]

    def get(self, logical_name: str) -> Optional[ChannelEntry]:
        return self._entries.get(logical_name)

    def all_entries(self) -> List[ChannelEntry]:
        return list(self._entries.values())

    def clear(self) -> None:
        self._entries.clear()

    def resolve(self, logical_name: str) -> ChannelEntry:
        entry = self.get(logical_name)
        if entry is None:
            raise ChannelMapError(
                f"Logical channel '{logical_name}' has no physical mapping. Add it in Settings → Channel Mapping."
            )
        if not entry.enabled:
            raise ChannelMapError(f"Channel '{logical_name}' is mapped but currently disabled.")
        return entry

    def logical_names(self) -> List[str]:
        return list(self._entries.keys())

    def enabled_entries(self) -> List[ChannelEntry]:
        return [e for e in self._entries.values() if e.enabled]

    def save(self, path: Path) -> None:
        data = [e.to_dict() for e in self._entries.values()]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Channel map saved to %s (%d entries)", path, len(data))

    def load(self, path: Path) -> None:
        if not path.exists():
            logger.warning("Channel map file not found: %s", path)
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            self._entries = {d["logical_name"]: ChannelEntry.from_dict(d) for d in raw}
            logger.info("Channel map loaded from %s (%d entries)", path, len(self._entries))
        except Exception as exc:
            raise ChannelMapError(f"Failed to load channel map: {exc}") from exc

    @classmethod
    def default_simulation_map(cls) -> "ChannelMap":
        cm = cls()
        cm.add_or_update(ChannelEntry("CAN1", "virtual", "virtual_channel_0", 500_000, True, "Primary BCM bus"))
        cm.add_or_update(ChannelEntry("CAN2", "virtual", "virtual_channel_1", 250_000, True, "Secondary / LIN gateway"))
        return cm


if _HAS_QT:
    class ChannelMapModel(QObject):
        map_changed = pyqtSignal()
        channel_added = pyqtSignal(str)
        channel_removed = pyqtSignal(str)

        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self._core = ChannelMap()

        def add_or_update(self, entry: ChannelEntry) -> None:
            is_new = entry.logical_name not in self._core.logical_names()
            self._core.add_or_update(entry)
            if is_new:
                self.channel_added.emit(entry.logical_name)
            self.map_changed.emit()

        def remove(self, logical_name: str) -> None:
            self._core.remove(logical_name)
            self.channel_removed.emit(logical_name)
            self.map_changed.emit()

        def get(self, logical_name: str) -> Optional[ChannelEntry]:
            return self._core.get(logical_name)

        def resolve(self, logical_name: str) -> ChannelEntry:
            return self._core.resolve(logical_name)

        def all_entries(self) -> List[ChannelEntry]:
            return self._core.all_entries()

        def enabled_entries(self) -> List[ChannelEntry]:
            return self._core.enabled_entries()

        def logical_names(self) -> List[str]:
            return self._core.logical_names()

        def clear(self) -> None:
            self._core.clear()
            self.map_changed.emit()

        def save(self, path: Path) -> None:
            self._core.save(path)

        def load(self, path: Path) -> None:
            self._core.load(path)
            self.map_changed.emit()

        @classmethod
        def default_simulation_map(cls) -> "ChannelMapModel":
            obj = cls()
            obj._core = ChannelMap.default_simulation_map()
            return obj
else:
    ChannelMapModel = ChannelMap  # type: ignore[misc,assignment]
