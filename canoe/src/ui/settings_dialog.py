"""
settings_dialog.py
------------------
Application Settings dialog that houses:

  Tab 1 – Connection Setup
          • Mode selector (Simulation / Hardware)
          • Hardware-specific options (interface adapter, bitrate)
          • DBC Upload panel — **shown only when mode == Simulation**

  Tab 2 – Channel Mapping
          • Inline channel-map editor (same as ChannelMapDialog but embedded)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QSpinBox,
    QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from src.can.channel_map import ChannelEntry, ChannelMap, ChannelMapModel, SUPPORTED_BUSTYPES
from src.ui.channel_entry_dialog import ChannelEntryDialog
from src.ui.dbc_upload_panel import DBCUploadPanel


class SettingsDialog(QDialog):
    settings_applied = pyqtSignal(str)
    _MODES = ["Simulation", "Hardware"]

    def __init__(
        self,
        channel_map_model: ChannelMapModel,
        dbc_panel: DBCUploadPanel,
        current_mode: str = "simulation",
        config_dir: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._model = channel_map_model
        self._dbc_panel = dbc_panel
        self._config_dir = config_dir or Path(".")
        self._current_mode = current_mode.lower()
        self._working: list[ChannelEntry] = [
            ChannelEntry(**{k: getattr(e, k) for k in ChannelEntry.__dataclass_fields__})
            for e in channel_map_model.all_entries()
        ]

        self.setWindowTitle("Settings")
        self.setMinimumSize(700, 500)
        self._build_ui()
        self._apply_mode(self._current_mode, init=True)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)
        tabs.addTab(self._build_connection_tab(), "Connection Setup")
        tabs.addTab(self._build_channel_map_tab(), "Channel Mapping")
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._ok)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Apply).clicked.connect(self._apply)
        root.addWidget(btns)

    def _build_connection_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        mode_group = QGroupBox("Operating Mode")
        mode_form = QFormLayout(mode_group)
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(self._MODES)
        idx = 0 if self._current_mode in ("simulation", "sim", "virtual") else 1
        self._mode_combo.setCurrentIndex(idx)
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_form.addRow("Mode:", self._mode_combo)
        self._mode_desc = QLabel()
        self._mode_desc.setWordWrap(True)
        self._mode_desc.setStyleSheet("color: grey; font-style: italic;")
        mode_form.addRow("", self._mode_desc)
        layout.addWidget(mode_group)

        self._hw_group = QGroupBox("Hardware Interface")
        hw_form = QFormLayout(self._hw_group)
        self._hw_bustype = QComboBox()
        self._hw_bustype.addItems([b for b in SUPPORTED_BUSTYPES if b != "virtual"])
        hw_form.addRow("Adapter Type:", self._hw_bustype)
        self._hw_channel = QComboBox()
        self._hw_channel.setEditable(True)
        self._hw_channel.addItems(["PCAN_USBBUS1", "vcan0", "can0", "0"])
        hw_form.addRow("Channel:", self._hw_channel)
        self._hw_bitrate = QSpinBox()
        self._hw_bitrate.setRange(10_000, 1_000_000)
        self._hw_bitrate.setSingleStep(50_000)
        self._hw_bitrate.setValue(500_000)
        self._hw_bitrate.setSuffix(" bps")
        hw_form.addRow("Bitrate:", self._hw_bitrate)
        self._hw_fd = QCheckBox("CAN FD")
        hw_form.addRow("", self._hw_fd)
        layout.addWidget(self._hw_group)
        layout.addWidget(self._dbc_panel)
        layout.addStretch()
        return tab

    def _build_channel_map_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        info = QLabel(
            "Map logical channel names to physical CAN adapters.\n"
            "These mappings apply in both Simulation and Hardware modes."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        cols = ["Logical Name", "Bus Type", "Channel", "Bitrate", "Enabled", "Description"]
        self._map_table = QTableWidget(0, len(cols))
        self._map_table.setHorizontalHeaderLabels(cols)
        self._map_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._map_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._map_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._map_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._map_table.doubleClicked.connect(self._cm_edit_selected)
        layout.addWidget(self._map_table)
        btn_row = QHBoxLayout()
        btn_add = QPushButton("Add")
        btn_edit = QPushButton("Edit")
        btn_rem = QPushButton("Remove")
        btn_def = QPushButton("Simulation Defaults")
        for b in (btn_add, btn_edit, btn_rem, btn_def):
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        btn_add.clicked.connect(self._cm_add)
        btn_edit.clicked.connect(self._cm_edit_selected)
        btn_rem.clicked.connect(self._cm_remove)
        btn_def.clicked.connect(self._cm_load_defaults)
        self._cm_populate()
        return tab

    def _on_mode_changed(self, mode_text: str) -> None:
        self._apply_mode(mode_text.lower())

    def _apply_mode(self, mode: str, init: bool = False) -> None:
        is_sim = mode in ("simulation", "sim", "virtual")
        self._hw_group.setVisible(not is_sim)
        self._dbc_panel.set_mode("simulation" if is_sim else "hardware")
        self._mode_desc.setText(
            "Simulation: uses virtual CAN channels. DBC upload is available below."
            if is_sim else
            "Hardware: connects to a real CAN adapter. DBC upload is disabled."
        )
        if not init:
            self._current_mode = mode

    def _cm_populate(self) -> None:
        self._map_table.setRowCount(0)
        for e in self._working:
            self._cm_append_row(e)

    def _cm_append_row(self, e: ChannelEntry) -> None:
        r = self._map_table.rowCount()
        self._map_table.insertRow(r)
        for col, val in enumerate([e.logical_name, e.bustype, e.channel, str(e.bitrate), "✓" if e.enabled else "✗", e.description]):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)
            self._map_table.setItem(r, col, item)

    def _cm_update_row(self, row: int, e: ChannelEntry) -> None:
        for col, val in enumerate([e.logical_name, e.bustype, e.channel, str(e.bitrate), "✓" if e.enabled else "✗", e.description]):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)
            self._map_table.setItem(row, col, item)

    def _cm_selected_row(self) -> int:
        rows = self._map_table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _cm_add(self) -> None:
        dlg = ChannelEntryDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            entry = dlg.get_entry()
            if any(e.logical_name == entry.logical_name for e in self._working):
                QMessageBox.warning(self, "Duplicate Name", f"'{entry.logical_name}' already exists.")
                return
            self._working.append(entry)
            self._cm_append_row(entry)

    def _cm_edit_selected(self) -> None:
        row = self._cm_selected_row()
        if row < 0:
            return
        dlg = ChannelEntryDialog(entry=self._working[row], parent=self)
        if dlg.exec_() == QDialog.Accepted:
            updated = dlg.get_entry()
            if updated.logical_name != self._working[row].logical_name:
                if any(e.logical_name == updated.logical_name for i, e in enumerate(self._working) if i != row):
                    QMessageBox.warning(self, "Duplicate Name", f"'{updated.logical_name}' already exists.")
                    return
            self._working[row] = updated
            self._cm_update_row(row, updated)

    def _cm_remove(self) -> None:
        row = self._cm_selected_row()
        if row < 0:
            return
        if QMessageBox.question(self, "Remove", f"Remove '{self._working[row].logical_name}'?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._working.pop(row)
            self._map_table.removeRow(row)

    def _cm_load_defaults(self) -> None:
        if QMessageBox.question(self, "Load Defaults", "Replace current mapping with simulation defaults?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._working = ChannelMap.default_simulation_map().all_entries()
            self._cm_populate()

    def _apply(self) -> None:
        self._model.clear()
        for e in self._working:
            try:
                self._model.add_or_update(e)
            except Exception as exc:
                QMessageBox.critical(self, "Invalid Mapping", str(exc))
                return
        save_path = self._config_dir / "channel_map.json"
        try:
            self._model.save(save_path)
        except Exception as exc:
            QMessageBox.warning(self, "Save Warning", f"Could not save channel map:\n{exc}")
        self.settings_applied.emit(self._mode_combo.currentText().lower())

    def _ok(self) -> None:
        self._apply()
        self.accept()
