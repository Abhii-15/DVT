"""
channel_entry_dialog.py
-----------------------
Small form dialog for creating or editing a single ChannelEntry.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QLineEdit, QMessageBox, QSpinBox, QWidget,
)

from src.can.channel_map import ChannelEntry, SUPPORTED_BUSTYPES


_CHANNEL_HINTS = {
    "virtual":   "virtual_channel_0",
    "socketcan": "vcan0",
    "pcan":      "PCAN_USBBUS1",
    "kvaser":    "0",
    "vector":    "0",
    "usb2can":   "COM3",
    "ixxat":     "0",
}


class ChannelEntryDialog(QDialog):
    def __init__(self, entry: Optional[ChannelEntry] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._editing = entry is not None
        self.setWindowTitle("Edit Channel" if self._editing else "Add Channel")
        self.setMinimumWidth(380)
        self._build_ui(entry)

    def _build_ui(self, entry: Optional[ChannelEntry]) -> None:
        form = QFormLayout(self)

        self._name_edit = QLineEdit(entry.logical_name if entry else "")
        self._name_edit.setPlaceholderText("e.g. CAN1, Powertrain, Body")
        form.addRow("Logical Name *", self._name_edit)

        self._bustype_combo = QComboBox()
        self._bustype_combo.addItems(SUPPORTED_BUSTYPES)
        if entry:
            idx = SUPPORTED_BUSTYPES.index(entry.bustype) if entry.bustype in SUPPORTED_BUSTYPES else 0
            self._bustype_combo.setCurrentIndex(idx)
        self._bustype_combo.currentTextChanged.connect(self._on_bustype_changed)
        form.addRow("Bus Type *", self._bustype_combo)

        self._channel_edit = QLineEdit(entry.channel if entry else "")
        self._update_channel_placeholder(self._bustype_combo.currentText())
        form.addRow("Channel *", self._channel_edit)

        self._bitrate_spin = QSpinBox()
        self._bitrate_spin.setRange(10_000, 1_000_000)
        self._bitrate_spin.setSingleStep(50_000)
        self._bitrate_spin.setSuffix(" bps")
        self._bitrate_spin.setValue(entry.bitrate if entry else 500_000)
        form.addRow("Bitrate", self._bitrate_spin)

        self._enabled_check = QCheckBox()
        self._enabled_check.setChecked(entry.enabled if entry else True)
        form.addRow("Enabled", self._enabled_check)

        self._desc_edit = QLineEdit(entry.description if entry else "")
        self._desc_edit.setPlaceholderText("Optional description")
        form.addRow("Description", self._desc_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_bustype_changed(self, bustype: str) -> None:
        self._update_channel_placeholder(bustype)

    def _update_channel_placeholder(self, bustype: str) -> None:
        self._channel_edit.setPlaceholderText(_CHANNEL_HINTS.get(bustype, "channel identifier"))

    def _validate_and_accept(self) -> None:
        name = self._name_edit.text().strip()
        channel = self._channel_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Logical Name is required.")
            return
        if not channel:
            QMessageBox.warning(self, "Validation", "Channel is required.")
            return
        self.accept()

    def get_entry(self) -> ChannelEntry:
        return ChannelEntry(
            logical_name=self._name_edit.text().strip(),
            bustype=self._bustype_combo.currentText(),
            channel=self._channel_edit.text().strip(),
            bitrate=self._bitrate_spin.value(),
            enabled=self._enabled_check.isChecked(),
            description=self._desc_edit.text().strip(),
        )
