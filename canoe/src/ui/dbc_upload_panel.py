"""
dbc_upload_panel.py
-------------------
Widget that lets the user upload / manage DBC files in Simulation mode only.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from PyQt5.QtCore import pyqtSignal, Qt
    from PyQt5.QtWidgets import (
        QFileDialog, QGroupBox, QHBoxLayout, QLabel,
        QListWidget, QListWidgetItem, QMessageBox,
        QPushButton, QVBoxLayout, QWidget,
    )
    _HAS_QT = True
except ImportError:
    _HAS_QT = False


def _parse_json_dbc(path: Path) -> Tuple[Dict, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    messages = raw.get("messages", {})
    msg_count = len(messages)
    sig_count = sum(len(m.get("signals", {})) for m in messages.values())
    summary = f"{msg_count} messages, {sig_count} signals"
    return raw, summary


def _parse_dbc_file(path: Path) -> Tuple[Dict, str]:
    try:
        import cantools
        db = cantools.database.load_file(str(path))
        summary = f"{len(db.messages)} messages, {sum(len(m.signals) for m in db.messages)} signals"
        db_dict: Dict = {"messages": {}}
        for msg in db.messages:
            db_dict["messages"][str(msg.frame_id)] = {
                "name": msg.name,
                "signals": {
                    s.name: {
                        "start_bit": s.start,
                        "length": s.length,
                        "byte_order": s.byte_order,
                        "scale": s.scale,
                        "offset": s.offset,
                        "minimum": s.minimum,
                        "maximum": s.maximum,
                        "unit": s.unit or "",
                    }
                    for s in msg.signals
                },
            }
        return db_dict, summary
    except ImportError:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        msg_count = sum(1 for l in lines if l.strip().startswith("BO_ "))
        sig_count = sum(1 for l in lines if l.strip().startswith("SG_ "))
        summary = f"~{msg_count} messages, ~{sig_count} signals (cantools not installed)"
        return {"_raw_lines": lines}, summary


if _HAS_QT:
    class DBCUploadPanel(QGroupBox):
        dbc_loaded = pyqtSignal(str, dict)  # database_name, db_dict
        dbc_removed = pyqtSignal(str)
        dbc_file_selected = pyqtSignal(str)

        _SIMULATION_MODES = {"simulation", "sim", "virtual"}

        def __init__(self, parent: Optional[QWidget] = None) -> None:
            super().__init__("DBC File Management  (Simulation Mode)", parent)
            self._loaded: Dict[str, dict] = {}
            self._mode: str = "simulation"
            self._build_ui()

        def set_mode(self, mode: str) -> None:
            self._mode = mode.lower()
            is_sim = self._mode in self._SIMULATION_MODES
            self.setVisible(is_sim)
            logger.debug("DBCUploadPanel visibility → %s (mode=%s)", is_sim, mode)

        def loaded_dbs(self) -> Dict[str, dict]:
            return dict(self._loaded)

        def get_combined_db(self) -> dict:
            combined: dict = {"messages": {}}
            for db in self._loaded.values():
                combined["messages"].update(db.get("messages", {}))
            return combined

        def _build_ui(self) -> None:
            layout = QVBoxLayout(self)

            note = QLabel("⚠  DBC upload is available in Simulation mode only.")
            note.setStyleSheet("color: #e67e22; font-style: italic;")
            note.setWordWrap(True)
            layout.addWidget(note)

            self._list = QListWidget()
            self._list.setMinimumHeight(100)
            layout.addWidget(self._list)

            btn_row = QHBoxLayout()
            self._btn_browse = QPushButton("Browse / Add DBC…")
            self._btn_remove = QPushButton("Remove Selected")
            self._btn_reload = QPushButton("Reload All")
            self._btn_clear = QPushButton("Clear All")
            for b in (self._btn_browse, self._btn_remove, self._btn_reload, self._btn_clear):
                btn_row.addWidget(b)
            btn_row.addStretch()
            layout.addLayout(btn_row)

            self._status_label = QLabel("No DBC files loaded.")
            self._status_label.setAlignment(Qt.AlignLeft)
            layout.addWidget(self._status_label)

            self._btn_browse.clicked.connect(self._browse)
            self._btn_remove.clicked.connect(self._remove_selected)
            self._btn_reload.clicked.connect(self._reload_all)
            self._btn_clear.clicked.connect(self._clear_all)

        def _browse(self) -> None:
            if self._mode not in self._SIMULATION_MODES:
                QMessageBox.information(
                    self, "Simulation Mode Only",
                    "DBC file upload is only available in Simulation mode.\nSwitch to Simulation mode first."
                )
                return
            files, _ = QFileDialog.getOpenFileNames(
                self, "Select DBC / JSON-DBC File(s)", "",
                "DBC Files (*.dbc *.json);;All Files (*)",
            )
            for f in files:
                self._load_file(Path(f))

        def _load_file(self, path: Path) -> None:
            if not path.exists():
                QMessageBox.warning(self, "File Not Found", f"Cannot find:\n{path}")
                return
            try:
                if path.suffix.lower() == ".json":
                    db_dict, summary = _parse_json_dbc(path)
                else:
                    db_dict, summary = _parse_dbc_file(path)
            except Exception as exc:
                QMessageBox.critical(self, "Parse Error", f"Failed to parse {path.name}:\n{exc}")
                logger.exception("DBC parse failed: %s", path)
                return

            path_str = str(path)
            is_update = path_str in self._loaded
            self._loaded[path_str] = db_dict

            label = f"{path.name}  —  {summary}"
            if is_update:
                for i in range(self._list.count()):
                    if self._list.item(i).data(Qt.UserRole) == path_str:
                        self._list.item(i).setText(label)
                        break
            else:
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, path_str)
                item.setToolTip(path_str)
                self._list.addItem(item)

            self._update_status()
            self.dbc_file_selected.emit(path_str)
            # Emit signal with database name and parsed data
            db_name = path.stem  # Use filename without extension
            self.dbc_loaded.emit(db_name, db_dict)
            logger.info("DBC loaded: %s (%s)", path.name, summary)

        def _remove_selected(self) -> None:
            for item in self._list.selectedItems():
                path_str = item.data(Qt.UserRole)
                self._loaded.pop(path_str, None)
                self._list.takeItem(self._list.row(item))
                self.dbc_removed.emit(path_str)
            self._update_status()

        def _reload_all(self) -> None:
            paths = list(self._loaded.keys())
            self._loaded.clear()
            self._list.clear()
            for p in paths:
                self._load_file(Path(p))

        def _clear_all(self) -> None:
            if QMessageBox.question(self, "Clear All", "Remove all loaded DBC files?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                for p in list(self._loaded.keys()):
                    self.dbc_removed.emit(p)
                self._loaded.clear()
                self._list.clear()
                self._update_status()

        def _update_status(self) -> None:
            n = len(self._loaded)
            self._status_label.setText(
                "No DBC files loaded." if n == 0 else f"{n} DBC file{'s' if n != 1 else ''} loaded."
            )
