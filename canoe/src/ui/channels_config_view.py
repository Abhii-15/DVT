"""
channels_config_view.py
-----------------------
UI panel for viewing and managing channel configurations.

Displays all available channels with their status, queue sizes, and database assignments.
"""

from typing import Dict, Optional

from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QHeaderView,
)

from src.can import ChannelManager


class ChannelsConfigView(QWidget):
    """
    Panel displaying all channel configurations and their status.

    Signals:
        channel_created(int, str): Emitted when a new channel is created
            Parameters: (channel_id, bus_type)
        channel_deleted(int): Emitted when a channel is deleted
            Parameters: (channel_id,)
    """

    channel_created = pyqtSignal(int, str)  # channel_id, bus_type
    channel_deleted = pyqtSignal(int)  # channel_id

    def __init__(self, channel_manager: ChannelManager):
        super().__init__()
        self._channel_manager = channel_manager
        self._row_to_channel_id: Dict[int, int] = {}

        self._init_ui()
        self._init_auto_refresh()

    def _init_ui(self) -> None:
        """Initialize the UI."""
        layout = QVBoxLayout()

        # Title
        title = QLabel("Channel Configurations")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Channel ID", "Bus Type", "Status", "TX Queue", "RX Queue"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        layout.addWidget(self._table)

        # Control buttons
        button_layout = QHBoxLayout()

        self._create_btn = QPushButton("Create Channel")
        self._create_btn.clicked.connect(self._show_create_channel_dialog)
        button_layout.addWidget(self._create_btn)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self.refresh_channels)
        button_layout.addWidget(self._refresh_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _init_auto_refresh(self) -> None:
        """Set up auto-refresh timer for queue sizes."""
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._update_queue_sizes)
        self._refresh_timer.start(500)  # Update every 500ms

    def refresh_channels(self) -> None:
        """Refresh the table with current channel status."""
        self._table.setRowCount(0)
        self._row_to_channel_id.clear()

        channels = self._channel_manager.get_all_channels()
        self._table.setRowCount(len(channels))

        for row, channel in enumerate(channels):
            # Channel ID
            id_item = QTableWidgetItem(str(channel.channel_id))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, 0, id_item)

            # Bus Type
            bustype_item = QTableWidgetItem(channel.bus_type)
            bustype_item.setFlags(bustype_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, 1, bustype_item)

            # Status
            status_text = "Active" if channel.is_active else "Inactive"
            status_item = QTableWidgetItem(status_text)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, 2, status_item)

            # TX Queue (updated separately)
            tx_item = QTableWidgetItem("")
            tx_item.setFlags(tx_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, 3, tx_item)

            # RX Queue (updated separately)
            rx_item = QTableWidgetItem("")
            rx_item.setFlags(rx_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, 4, rx_item)

            self._row_to_channel_id[row] = channel.channel_id

        # Initial queue size update
        self._update_queue_sizes()

    def _update_queue_sizes(self) -> None:
        """Update queue size display (called periodically)."""
        for row, channel_id in self._row_to_channel_id.items():
            channel = self._channel_manager.get_channel(channel_id)
            if channel:
                tx_size = channel._tx_queue.qsize()
                rx_size = channel._rx_queue.qsize()

                self._table.item(row, 3).setText(str(tx_size))
                self._table.item(row, 4).setText(str(rx_size))

    def _show_create_channel_dialog(self) -> None:
        """Show dialog to create a new channel."""
        # TODO: Implement a dialog for channel creation
        # For now, create a CAN channel programmatically
        channel = self._channel_manager.create_channel("CAN")
        self.channel_created.emit(channel.channel_id, channel.bus_type)
        self.refresh_channels()

    @pyqtSlot()
    def on_channel_created(self) -> None:
        """Refresh when a channel is created externally."""
        self.refresh_channels()

    @pyqtSlot()
    def on_channel_deleted(self, channel_id: int) -> None:
        """Refresh when a channel is deleted externally."""
        self.refresh_channels()

    def get_all_channels(self) -> list:
        """Return list of all channels."""
        return self._channel_manager.get_all_channels()

    def set_enable(self, enabled: bool) -> None:
        """Enable/disable the panel."""
        self._table.setEnabled(enabled)
        self._create_btn.setEnabled(enabled)
        self._refresh_btn.setEnabled(enabled)

    def closeEvent(self, event) -> None:
        """Clean up timer on close."""
        self._refresh_timer.stop()
        super().closeEvent(event)
