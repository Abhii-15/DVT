from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.can.can_manager import CANManager
from src.simulation.scheduler import CyclicScheduler


class HardwareTabMixin:
    def _build_hw_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        hdr = QLabel('Hardware Setup')
        hdr.setStyleSheet('font-size:16px; font-weight:bold; color:#7ab8f5;')
        lay.addWidget(hdr)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        mapping_group = QGroupBox('CAN Channel Mapping')
        mapping_layout = QVBoxLayout(mapping_group)

        self.hw_map_table = QTableWidget(0, 6)
        self.hw_map_table.setHorizontalHeaderLabels(['Node', 'Interface', 'Channel', 'Bitrate', 'Mode', 'State'])
        self.hw_map_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.hw_map_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.hw_map_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.hw_map_table.itemSelectionChanged.connect(self._on_hw_row_selected)
        mapping_layout.addWidget(self.hw_map_table)

        row_buttons = QHBoxLayout()
        add_btn = QPushButton('Add Mapping')
        add_btn.clicked.connect(self._add_hw_mapping_row)
        row_buttons.addWidget(add_btn)
        remove_btn = QPushButton('Remove Mapping')
        remove_btn.clicked.connect(self._remove_hw_mapping_row)
        row_buttons.addWidget(remove_btn)
        row_buttons.addStretch()
        mapping_layout.addLayout(row_buttons)

        left_layout.addWidget(mapping_group)

        config_group = QGroupBox('Selected Mapping Configuration')
        grid = QGridLayout(config_group)

        self.hw_node_name = QLineEdit('BCM')
        self.hw_iface_type = QComboBox()
        self.hw_iface_type.addItems(['virtual', 'pcan', 'vector', 'kvaser', 'socketcan'])
        self.hw_channel = QLineEdit('test')
        self.hw_baud = QComboBox()
        self.hw_baud.addItems(['125', '250', '500', '1000'])
        self.hw_baud.setCurrentText('500')
        self.hw_mode = QComboBox()
        self.hw_mode.addItems(['Simulation', 'Measurement', 'Monitoring'])

        grid.addWidget(QLabel('Node Name'), 0, 0)
        grid.addWidget(self.hw_node_name, 0, 1)
        grid.addWidget(QLabel('Interface'), 1, 0)
        grid.addWidget(self.hw_iface_type, 1, 1)
        grid.addWidget(QLabel('Channel'), 2, 0)
        grid.addWidget(self.hw_channel, 2, 1)
        grid.addWidget(QLabel('Bitrate (kbps)'), 3, 0)
        grid.addWidget(self.hw_baud, 3, 1)
        grid.addWidget(QLabel('Mode'), 4, 0)
        grid.addWidget(self.hw_mode, 4, 1)

        cfg_buttons = QHBoxLayout()
        self.hw_connect_btn = QPushButton('Connect Selected')
        self.hw_connect_btn.clicked.connect(self._hw_connect)
        cfg_buttons.addWidget(self.hw_connect_btn)
        self.hw_disconnect_btn = QPushButton('Disconnect')
        self.hw_disconnect_btn.clicked.connect(self._hw_disconnect)
        cfg_buttons.addWidget(self.hw_disconnect_btn)
        self.hw_apply_btn = QPushButton('Apply to Table')
        self.hw_apply_btn.clicked.connect(self._apply_hw_mapping_to_row)
        cfg_buttons.addWidget(self.hw_apply_btn)
        cfg_buttons.addStretch()

        grid.addLayout(cfg_buttons, 5, 0, 1, 2)
        left_layout.addWidget(config_group)

        self.hw_status = QLabel('Status: Not connected')
        self.hw_status.setStyleSheet('color:#e07070; font-weight:bold;')
        left_layout.addWidget(self.hw_status)
        left_layout.addStretch()
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        dbc_group = QGroupBox('Network & DBC')
        dbc_layout = QVBoxLayout(dbc_group)
        dbc_layout.addWidget(QLabel('Loaded DBC:'))
        self.hw_dbc_label = QLabel('None')
        self.hw_dbc_label.setStyleSheet('color:#7ab8f5; font-weight:bold;')
        dbc_layout.addWidget(self.hw_dbc_label)
        load_dbc_btn = QPushButton('Load DBC File…')
        load_dbc_btn.clicked.connect(self._load_dbc)
        dbc_layout.addWidget(load_dbc_btn)
        dbc_layout.addSpacing(10)
        dbc_layout.addWidget(QLabel('Add Node to Canvas:'))
        self.hw_node_name_canvas = QLineEdit()
        self.hw_node_name_canvas.setPlaceholderText('e.g. ECU_BCM')
        dbc_layout.addWidget(self.hw_node_name_canvas)
        add_node_btn = QPushButton('Add Node')
        add_node_btn.clicked.connect(self._add_node_from_hw)
        dbc_layout.addWidget(add_node_btn)
        dbc_layout.addStretch()
        right_layout.addWidget(dbc_group)

        summary_group = QGroupBox('Connection Summary')
        summary_layout = QVBoxLayout(summary_group)
        self.hw_summary = QLabel('Pick a mapping, connect the bus, and start measurement.')
        self.hw_summary.setWordWrap(True)
        self.hw_summary.setStyleSheet('color:#b7c6d9;')
        summary_layout.addWidget(self.hw_summary)
        right_layout.addWidget(summary_group)
        right_layout.addStretch()

        splitter.addWidget(right)
        splitter.setSizes([780, 420])
        lay.addWidget(splitter)
        self.main_tabs.addTab(tab, 'Hardware Setup')

        self._add_hw_mapping_row(default=True)

    def _default_hw_row_values(self):
        return {
            'node': 'BCM',
            'interface': 'virtual',
            'channel': 'test',
            'bitrate': '500',
            'mode': 'Simulation',
            'state': 'Disconnected',
        }

    def _selected_hw_row(self):
        selection = self.hw_map_table.selectionModel().selectedRows() if self.hw_map_table.selectionModel() else []
        return selection[0].row() if selection else -1

    def _on_hw_row_selected(self):
        row = self._selected_hw_row()
        if row >= 0:
            self._sync_hw_fields_from_row(row)
            self._update_hw_summary()

    def _sync_hw_fields_from_row(self, row):
        if row < 0:
            return
        self.hw_node_name.setText(self.hw_map_table.item(row, 0).text())
        self.hw_iface_type.setCurrentText(self.hw_map_table.item(row, 1).text())
        self.hw_channel.setText(self.hw_map_table.item(row, 2).text())
        self.hw_baud.setCurrentText(self.hw_map_table.item(row, 3).text())
        self.hw_mode.setCurrentText(self.hw_map_table.item(row, 4).text())

    def _add_hw_mapping_row(self, default=False):
        values = self._default_hw_row_values() if default else {
            'node': self.hw_node_name.text().strip() or f'Node_{self.hw_map_table.rowCount() + 1}',
            'interface': self.hw_iface_type.currentText(),
            'channel': self.hw_channel.text().strip() or 'test',
            'bitrate': self.hw_baud.currentText(),
            'mode': self.hw_mode.currentText(),
            'state': 'Disconnected',
        }
        row = self.hw_map_table.rowCount()
        self.hw_map_table.insertRow(row)
        for col, key in enumerate(['node', 'interface', 'channel', 'bitrate', 'mode', 'state']):
            self.hw_map_table.setItem(row, col, QTableWidgetItem(values[key]))
        self.hw_map_table.selectRow(row)
        self._sync_hw_fields_from_row(row)
        self._update_hw_summary()

    def _remove_hw_mapping_row(self):
        row = self._selected_hw_row()
        if row < 0:
            return
        self.hw_map_table.removeRow(row)
        if self.hw_map_table.rowCount() > 0:
            self.hw_map_table.selectRow(max(0, row - 1))
        self._update_hw_summary()

    def _apply_hw_mapping_to_row(self):
        row = self._selected_hw_row()
        if row < 0:
            self._add_hw_mapping_row()
            return
        values = [
            self.hw_node_name.text().strip() or self.hw_map_table.item(row, 0).text(),
            self.hw_iface_type.currentText(),
            self.hw_channel.text().strip() or self.hw_map_table.item(row, 2).text(),
            self.hw_baud.currentText(),
            self.hw_mode.currentText(),
            self.hw_map_table.item(row, 5).text() if self.hw_map_table.item(row, 5) else 'Disconnected',
        ]
        for col, value in enumerate(values):
            self.hw_map_table.setItem(row, col, QTableWidgetItem(value))
        self._update_hw_summary()

    def _update_hw_summary(self):
        row = self._selected_hw_row()
        if row < 0:
            self.hw_summary.setText('No mapping selected.')
            return
        node = self.hw_map_table.item(row, 0).text()
        iface = self.hw_map_table.item(row, 1).text()
        channel = self.hw_map_table.item(row, 2).text()
        bitrate = self.hw_map_table.item(row, 3).text()
        mode = self.hw_map_table.item(row, 4).text()
        state = self.hw_map_table.item(row, 5).text()
        self.hw_summary.setText(
            f'Node {node} is mapped to {iface.upper()} on channel {channel} at {bitrate} kbps in {mode} mode. State: {state}.'
        )

    def _hw_connect(self):
        try:
            row = self._selected_hw_row()
            if row < 0:
                self._add_hw_mapping_row(default=False)
                row = self._selected_hw_row()
            interface_type = self.hw_map_table.item(row, 1).text()
            channel = self.hw_map_table.item(row, 2).text().strip() or 'test'
            bitrate = int(self.hw_map_table.item(row, 3).text())
            self.can_if.connect(channel=channel, bustype=interface_type, bitrate=bitrate, allow_fallback=True)
            self.scheduler = CyclicScheduler(self.can_if)
            if self.measurement_running:
                self._start_dbc_stimulation()
            self.hw_map_table.setItem(row, 5, QTableWidgetItem('Connected'))
            self.hw_status.setText(
                f'Status: Connected ({self.can_if.bustype}/{self.can_if.channel} @ {self.can_if.bitrate} kbps)'
            )
            self.hw_status.setStyleSheet('color:#44dd44; font-weight:bold;')
            self._update_status_labels()
            self._update_hw_summary()
            self._log(f'CAN connected using {self.can_if.bustype} on {self.can_if.channel}')
            self.statusBar().showMessage(f'Connected: {self.can_if.bustype} on {self.can_if.channel}')
        except Exception as e:
            self.hw_status.setText(f'Status: Error — {e}')
            self.hw_status.setStyleSheet('color:#e07070; font-weight:bold;')
            QMessageBox.warning(self, 'Connection Error', str(e))

    def _hw_disconnect(self):
        try:
            self.can_if.disconnect()
            row = self._selected_hw_row()
            if row >= 0:
                self.hw_map_table.setItem(row, 5, QTableWidgetItem('Disconnected'))
            self.hw_status.setText('Status: Not connected')
            self.hw_status.setStyleSheet('color:#e07070; font-weight:bold;')
            self._update_status_labels()
            self._update_hw_summary()
            self._log('CAN bus disconnected')
            self.statusBar().showMessage('CAN disconnected')
        except Exception as e:
            QMessageBox.warning(self, 'Disconnect Error', str(e))

    def _add_node_from_hw(self):
        name = self.hw_node_name_canvas.text().strip()
        if name:
            self.bus_canvas.add_node(name)
            self.hw_node_name_canvas.clear()
            self.statusBar().showMessage(f"Node '{name}' added")
        else:
            QMessageBox.information(self, 'Add Node', 'Enter a node name first.')
