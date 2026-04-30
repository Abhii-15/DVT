"""
channel_map_dialog.py
---------------------
PyQt5 dialog for editing the channel map.

Shows a table of logical → physical mappings and provides Add / Edit /
Remove buttons. Changes are not committed to the model until the user
clicks OK (cancel rolls back all edits).
"""

from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.can.channel_map import ChannelEntry, ChannelMap, ChannelMapModel
from src.ui.channel_entry_dialog import ChannelEntryDialog


class ChannelMapDialog(QDialog):
    _COLUMNS = ["Logical Name", "Bus Type", "Channel", "Bitrate (bps)", "Enabled", "Description"]

    def __init__(self, model: ChannelMapModel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._model = model
        self._working: List[ChannelEntry] = [
            ChannelEntry(**{k: getattr(e, k) for k in ChannelEntry.__dataclass_fields__})
            for e in model.all_entries()
        ]

        self.setWindowTitle("Channel Mapping")
        self.setMinimumSize(750, 380)
        self._build_ui()
        self._populate_table()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Map logical channel names to physical CAN interface adapters.\n"
            "These mappings are used by all CAN bus operations in the tool."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._table = QTableWidget(0, len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels(self._COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.doubleClicked.connect(self._edit_selected)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        self._btn_add = QPushButton("Add Channel")
        self._btn_edit = QPushButton("Edit")
        self._btn_remove = QPushButton("Remove")
        self._btn_defaults = QPushButton("Load Simulation Defaults")
        for b in (self._btn_add, self._btn_edit, self._btn_remove, self._btn_defaults):
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._btn_add.clicked.connect(self._add_channel)
        self._btn_edit.clicked.connect(self._edit_selected)
        self._btn_remove.clicked.connect(self._remove_selected)
        self._btn_defaults.clicked.connect(self._load_defaults)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._commit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_table(self) -> None:
        self._table.setRowCount(0)
        for entry in self._working:
            self._append_row(entry)

    def _append_row(self, entry: ChannelEntry) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        values = [
            entry.logical_name,
            entry.bustype,
            entry.channel,
            str(entry.bitrate),
            "✓" if entry.enabled else "✗",
            entry.description,
        ]
        for col, val in enumerate(values):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, col, item)

    def _update_row(self, row: int, entry: ChannelEntry) -> None:
        values = [
            entry.logical_name,
            entry.bustype,
            entry.channel,
            str(entry.bitrate),
            "✓" if entry.enabled else "✗",
            entry.description,
        ]
        for col, val in enumerate(values):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, col, item)

    def _selected_row(self) -> int:
        rows = self._table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _add_channel(self) -> None:
        dlg = ChannelEntryDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            entry = dlg.get_entry()
            if any(e.logical_name == entry.logical_name for e in self._working):
                QMessageBox.warning(self, "Duplicate Name", f"A channel named '{entry.logical_name}' already exists.")
                return
            self._working.append(entry)
            self._append_row(entry)

    def _edit_selected(self) -> None:
        row = self._selected_row()
        if row < 0:
            return
        entry = self._working[row]
        dlg = ChannelEntryDialog(entry=entry, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            updated = dlg.get_entry()
            if updated.logical_name != entry.logical_name:
                if any(e.logical_name == updated.logical_name for i, e in enumerate(self._working) if i != row):
                    QMessageBox.warning(self, "Duplicate Name", f"A channel named '{updated.logical_name}' already exists.")
                    return
            self._working[row] = updated
            self._update_row(row, updated)

    def _remove_selected(self) -> None:
        row = self._selected_row()
        if row < 0:
            return
        name = self._working[row].logical_name
        resp = QMessageBox.question(self, "Remove Channel", f"Remove mapping for '{name}'?", QMessageBox.Yes | QMessageBox.No)
        if resp == QMessageBox.Yes:
            self._working.pop(row)
            self._table.removeRow(row)

    def _load_defaults(self) -> None:
        resp = QMessageBox.question(
            self, "Load Defaults",
            "This will replace the current mapping with simulation defaults.\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp == QMessageBox.Yes:
            defaults = ChannelMap.default_simulation_map()
            self._working = defaults.all_entries()
            self._populate_table()

    def _commit(self) -> None:
        self._model.clear()
        for entry in self._working:
            try:
                self._model.add_or_update(entry)
            except Exception as exc:
                QMessageBox.critical(self, "Invalid Mapping", str(exc))
                return
        self.accept()
