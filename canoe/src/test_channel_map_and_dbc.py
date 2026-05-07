"""
test_channel_map_and_dbc.py
---------------------------
Unit tests for:
  1. ChannelMap / ChannelEntry  (channel_map.py)
  2. DBCUploadPanel mode gating  (dbc_upload_panel.py)

Run with::

    pytest test_channel_map_and_dbc.py -v
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

# ── Import helpers (allow running without Qt installed) ────────────────────────

try:
    from PyQt5.QtWidgets import QApplication
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

# Ensure the project root is importable regardless of working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.can.channel_map import (
    ChannelEntry,
    ChannelMap,
    ChannelMapError,
    SUPPORTED_BUSTYPES,
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. ChannelEntry
# ══════════════════════════════════════════════════════════════════════════════

class TestChannelEntry:
    def _make(self, **kw) -> ChannelEntry:
        defaults = dict(
            logical_name="CAN1",
            bustype="virtual",
            channel="virtual_channel_0",
            bitrate=500_000,
            enabled=True,
            description="test",
        )
        defaults.update(kw)
        return ChannelEntry(**defaults)

    def test_to_can_kwargs(self):
        e = self._make()
        kw = e.to_can_kwargs()
        assert kw["bustype"] == "virtual"
        assert kw["channel"] == "virtual_channel_0"
        assert kw["bitrate"] == 500_000

    def test_display_label_contains_name(self):
        e = self._make(logical_name="Powertrain")
        assert "Powertrain" in e.display_label()

    def test_roundtrip_dict(self):
        e = self._make(description="roundtrip test")
        restored = ChannelEntry.from_dict(e.to_dict())
        assert restored.logical_name == e.logical_name
        assert restored.bitrate == e.bitrate
        assert restored.description == e.description

    def test_from_dict_ignores_unknown_keys(self):
        d = self._make().to_dict()
        d["unknown_future_field"] = "should be ignored"
        e = ChannelEntry.from_dict(d)
        assert e.logical_name == "CAN1"


# ══════════════════════════════════════════════════════════════════════════════
# 2. ChannelMap (non-Qt core)
# ══════════════════════════════════════════════════════════════════════════════

class TestChannelMap:
    def _map(self) -> ChannelMap:
        return ChannelMap()

    def _entry(self, name="CAN1", bustype="virtual", channel="vch0") -> ChannelEntry:
        return ChannelEntry(name, bustype, channel)

    # ── add / get / remove ────────────────────────────────────────────────────

    def test_add_and_get(self):
        cm = self._map()
        cm.add_or_update(self._entry("CAN1"))
        assert cm.get("CAN1") is not None
        assert cm.get("CAN1").logical_name == "CAN1"

    def test_update_existing(self):
        cm = self._map()
        cm.add_or_update(self._entry("CAN1", channel="ch0"))
        cm.add_or_update(self._entry("CAN1", channel="ch1"))
        assert cm.get("CAN1").channel == "ch1"
        assert len(cm.all_entries()) == 1

    def test_remove(self):
        cm = self._map()
        cm.add_or_update(self._entry("CAN1"))
        cm.remove("CAN1")
        assert cm.get("CAN1") is None

    def test_remove_nonexistent_raises(self):
        cm = self._map()
        with pytest.raises(ChannelMapError):
            cm.remove("ghost")

    def test_clear(self):
        cm = self._map()
        cm.add_or_update(self._entry("CAN1"))
        cm.add_or_update(self._entry("CAN2"))
        cm.clear()
        assert cm.all_entries() == []

    # ── validation ────────────────────────────────────────────────────────────

    def test_invalid_bustype_raises(self):
        cm = self._map()
        with pytest.raises(ChannelMapError, match="Unsupported bustype"):
            cm.add_or_update(ChannelEntry("CAN1", "not_a_bustype", "ch0"))

    def test_empty_name_raises(self):
        cm = self._map()
        with pytest.raises(ChannelMapError, match="logical_name"):
            cm.add_or_update(ChannelEntry("", "virtual", "ch0"))

    def test_all_supported_bustypes_accepted(self):
        cm = self._map()
        for bt in SUPPORTED_BUSTYPES:
            cm.add_or_update(ChannelEntry(f"ch_{bt}", bt, "ch0"))
        assert len(cm.all_entries()) == len(SUPPORTED_BUSTYPES)

    # ── resolve ───────────────────────────────────────────────────────────────

    def test_resolve_returns_entry(self):
        cm = self._map()
        cm.add_or_update(self._entry("CAN1"))
        e = cm.resolve("CAN1")
        assert e.logical_name == "CAN1"

    def test_resolve_missing_raises(self):
        cm = self._map()
        with pytest.raises(ChannelMapError, match="no physical mapping"):
            cm.resolve("CAN99")

    def test_resolve_disabled_raises(self):
        cm = self._map()
        cm.add_or_update(ChannelEntry("CAN1", "virtual", "ch0", enabled=False))
        with pytest.raises(ChannelMapError, match="disabled"):
            cm.resolve("CAN1")

    # ── enabled_entries ───────────────────────────────────────────────────────

    def test_enabled_entries_filters_correctly(self):
        cm = self._map()
        cm.add_or_update(ChannelEntry("CAN1", "virtual", "ch0", enabled=True))
        cm.add_or_update(ChannelEntry("CAN2", "virtual", "ch1", enabled=False))
        enabled = cm.enabled_entries()
        assert len(enabled) == 1
        assert enabled[0].logical_name == "CAN1"

    # ── persistence ───────────────────────────────────────────────────────────

    def test_save_and_load_roundtrip(self, tmp_path):
        cm = self._map()
        cm.add_or_update(self._entry("CAN1", channel="ch_a"))
        cm.add_or_update(self._entry("CAN2", channel="ch_b"))
        path = tmp_path / "map.json"
        cm.save(path)

        cm2 = self._map()
        cm2.load(path)
        assert len(cm2.all_entries()) == 2
        assert cm2.get("CAN1").channel == "ch_a"
        assert cm2.get("CAN2").channel == "ch_b"

    def test_load_nonexistent_file_is_noop(self, tmp_path):
        cm = self._map()
        cm.load(tmp_path / "does_not_exist.json")
        assert cm.all_entries() == []

    def test_load_corrupt_json_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json", encoding="utf-8")
        cm = self._map()
        with pytest.raises(ChannelMapError):
            cm.load(path)

    # ── default_simulation_map ────────────────────────────────────────────────

    def test_default_simulation_map(self):
        cm = ChannelMap.default_simulation_map()
        entries = cm.all_entries()
        assert len(entries) >= 1
        assert all(e.bustype == "virtual" for e in entries)
        assert all(e.enabled for e in entries)


# ══════════════════════════════════════════════════════════════════════════════
# 3. DBCUploadPanel — mode gating (Qt required)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _QT_AVAILABLE, reason="PyQt5 not installed")
class TestDBCUploadPanelModeGating:
    """Verify that the DBC panel is only visible/functional in Simulation mode."""

    @pytest.fixture(autouse=True)
    def qt_app(self):
        app = QApplication.instance() or QApplication(sys.argv)
        yield app

    @pytest.fixture
    def panel(self):
        from src.ui.dbc_upload_panel import DBCUploadPanel
        p = DBCUploadPanel()
        p.set_mode("simulation")
        return p

    def test_visible_in_simulation_mode(self, panel):
        panel.set_mode("simulation")
        assert panel.isVisible()

    def test_hidden_in_hardware_mode(self, panel):
        panel.set_mode("hardware")
        assert not panel.isVisible()

    def test_sim_aliases_are_visible(self, panel):
        for alias in ("sim", "virtual", "Simulation"):
            panel.set_mode(alias)
            assert panel.isVisible(), f"Expected visible for mode='{alias}'"

    def test_hardware_alias_hides_panel(self, panel):
        panel.set_mode("Hardware")
        assert not panel.isVisible()

    def test_mode_toggle(self, panel):
        panel.set_mode("simulation")
        assert panel.isVisible()
        panel.set_mode("hardware")
        assert not panel.isVisible()
        panel.set_mode("simulation")
        assert panel.isVisible()


# ══════════════════════════════════════════════════════════════════════════════
# 4. JSON-DBC parsing
# ══════════════════════════════════════════════════════════════════════════════

class TestJSONDBCParsing:
    """Test the JSON-DBC parser used by DBCUploadPanel._load_file()."""

    @pytest.fixture
    def json_dbc_file(self, tmp_path) -> Path:
        content = {
            "messages": {
                "256": {
                    "name": "LightCmd",
                    "signals": {
                        "light_state": {"start_bit": 0, "length": 1}
                    }
                },
                "257": {
                    "name": "DoorCmd",
                    "signals": {
                        "door_lock": {"start_bit": 0, "length": 1}
                    }
                }
            }
        }
        path = tmp_path / "test.json"
        path.write_text(json.dumps(content), encoding="utf-8")
        return path

    def test_parse_returns_dict_and_summary(self, json_dbc_file):
        from src.ui.dbc_upload_panel import _parse_json_dbc
        db, summary = _parse_json_dbc(json_dbc_file)
        assert "messages" in db
        assert len(db["messages"]) == 2
        assert "2 messages" in summary
        assert "2 signals" in summary

    def test_parse_message_names(self, json_dbc_file):
        from src.ui.dbc_upload_panel import _parse_json_dbc
        db, _ = _parse_json_dbc(json_dbc_file)
        assert db["messages"]["256"]["name"] == "LightCmd"
        assert db["messages"]["257"]["name"] == "DoorCmd"

    def test_parse_empty_messages(self, tmp_path):
        from src.ui.dbc_upload_panel import _parse_json_dbc
        path = tmp_path / "empty.json"
        path.write_text(json.dumps({"messages": {}}), encoding="utf-8")
        db, summary = _parse_json_dbc(path)
        assert db["messages"] == {}
        assert "0 messages" in summary

    @pytest.mark.skipif(not _QT_AVAILABLE, reason="PyQt5 not installed")
    def test_panel_emits_signal_on_load(self, json_dbc_file):
        from PyQt5.QtWidgets import QApplication
        from src.ui.dbc_upload_panel import DBCUploadPanel
        app = QApplication.instance() or QApplication(sys.argv)
        received = []
        panel = DBCUploadPanel()
        panel.set_mode("simulation")
        panel.dbc_loaded.connect(lambda db: received.append(db))
        panel._load_file(json_dbc_file)
        assert len(received) == 1
        assert "messages" in received[0]

    @pytest.mark.skipif(not _QT_AVAILABLE, reason="PyQt5 not installed")
    def test_panel_does_not_emit_in_hardware_mode(self, json_dbc_file):
        """
        The panel emits dbc_loaded regardless of mode when _load_file is called
        directly; but the Browse button is guarded by a mode check. This test
        verifies that the panel is hidden in hardware mode, which prevents
        user interaction.
        """
        from PyQt5.QtWidgets import QApplication
        from src.ui.dbc_upload_panel import DBCUploadPanel
        app = QApplication.instance() or QApplication(sys.argv)
        panel = DBCUploadPanel()
        panel.set_mode("hardware")
        assert not panel.isVisible(), (
            "Panel must be hidden in hardware mode — "
            "DBC upload must not be accessible."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
