"""
channel_mapping_panel.py
------------------------
UI panel for displaying and managing channel mappings.

Shows a table with Database Name, Bus Type (inferred), and Assigned Channel dropdown.
"""

from typing import Optional, List, Dict, Any

from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QPushButton,
    QLabel,
    QHeaderView,
)

from src.can import DatabaseManager, ChannelManager, Router


class ChannelMappingPanel(QWidget):
    """
    Panel displaying current database-to-channel assignments.

    Signals:
        database_assigned(str, int): Emitted when a database is assigned to a channel
            Parameters: (database_name, channel_id)
        database_unassigned(str): Emitted when a database is unassigned
            Parameters: (database_name,)
    """

    database_assigned = pyqtSignal(str, int)  # database_name, channel_id
    database_unassigned = pyqtSignal(str)  # database_name

    def __init__(
        self,
        database_manager: DatabaseManager,
        channel_manager: ChannelManager,
        router: Router,
    ):
        super().__init__()
        self._database_manager = database_manager
        self._channel_manager = channel_manager
        self._router = router

        self._dropdowns: Dict[str, QComboBox] = {}
        self._row_to_database: Dict[int, str] = {}

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the UI."""
        layout = QVBoxLayout()

        # Title
        title = QLabel("Database to Channel Mapping")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Database Name", "Messages", "Assigned Channel", "Actions"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self._table)

        # Refresh button
        button_layout = QHBoxLayout()
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self.refresh_mappings)
        button_layout.addStretch()
        button_layout.addWidget(self._refresh_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def refresh_mappings(self) -> None:
        """Refresh the table with current database/channel assignments."""
        self._table.setRowCount(0)
        self._dropdowns.clear()
        self._row_to_database.clear()

        databases = self._database_manager.get_all_databases()
        self._table.setRowCount(len(databases))

        for row, db in enumerate(databases):
            # Database Name
            name_item = QTableWidgetItem(db.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, 0, name_item)

            # Message Count
            msg_count = len(db.messages)
            msg_item = QTableWidgetItem(str(msg_count))
            msg_item.setFlags(msg_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, 1, msg_item)

            # Assigned Channel Dropdown
            dropdown = QComboBox()
            dropdown.addItem("None", -1)

            # Add all available channels
            for channel in self._channel_manager._channels.values():
                display_text = f"Channel {channel.channel_id} ({channel.bus_type})"
                dropdown.addItem(display_text, channel.channel_id)

            # Set current selection
            if db.assigned_channel is not None:
                for i in range(dropdown.count()):
                    if dropdown.itemData(i) == db.assigned_channel:
                        dropdown.setCurrentIndex(i)
                        break

            # Connect signal
            dropdown.currentIndexChanged.connect(
                lambda _checked, d=db.name: self._on_channel_selected(d)
            )

            self._dropdowns[db.name] = dropdown
            self._table.setCellWidget(row, 2, dropdown)

            # Unassign Button
            unassign_btn = QPushButton("Unassign")
            unassign_btn.clicked.connect(
                lambda _checked, d=db.name: self._on_unassign_clicked(d)
            )
            unassign_btn.setEnabled(db.assigned_channel is not None)
            self._table.setCellWidget(row, 3, unassign_btn)

            self._row_to_database[row] = db.name

    @pyqtSlot(str)
    def _on_channel_selected(self, database_name: str) -> None:
        """Handle channel selection in dropdown."""
        dropdown = self._dropdowns.get(database_name)
        if dropdown is None:
            return

        channel_id = dropdown.currentData()
        if channel_id == -1:
            # User selected "None"
            self._database_manager.unassign_from_channel(database_name)
            self.database_unassigned.emit(database_name)
        else:
            # User selected a channel
            self._database_manager.assign_to_channel(database_name, channel_id)
            self._router.rebuild_routing_map()
            self.database_assigned.emit(database_name, channel_id)

        # Refresh to update button states
        self.refresh_mappings()

    @pyqtSlot(str)
    def _on_unassign_clicked(self, database_name: str) -> None:
        """Handle unassign button click."""
        self._database_manager.unassign_from_channel(database_name)
        self._router.rebuild_routing_map()
        self.database_unassigned.emit(database_name)
        self.refresh_mappings()

    def on_database_added(self, database_name: str) -> None:
        """Called when a new database is added (external signal)."""
        self.refresh_mappings()

    def on_database_removed(self, database_name: str) -> None:
        """Called when a database is removed (external signal)."""
        self.refresh_mappings()

    def on_channel_created(self, channel_id: int, bus_type: str) -> None:
        """Called when a new channel is created (external signal)."""
        # Refresh to show new channel in dropdowns
        self.refresh_mappings()

    def on_channel_deleted(self, channel_id: int) -> None:
        """Called when a channel is deleted (external signal)."""
        # Auto-unassign any databases on this channel
        for db in self._database_manager.get_all_databases():
            if db.assigned_channel == channel_id:
                self._database_manager.unassign_from_channel(db.name)
        self._router.rebuild_routing_map()
        self.refresh_mappings()

    def get_current_mappings(self) -> Dict[str, Optional[int]]:
        """Return current database -> channel mappings."""
        return self._database_manager.get_all_assigned_channels()

    def set_enable(self, enabled: bool) -> None:
        """Enable/disable the panel."""
        self._table.setEnabled(enabled)
        self._refresh_btn.setEnabled(enabled)
