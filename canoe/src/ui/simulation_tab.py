import contextlib
import io
import json
import time

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QFileDialog, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget

from src.simulation.message_catalog import MessageCatalog
from src.simulation.simulation_canvas import CANBusGraphicsView


class SimulationTabMixin:
    def _build_simulation_tab(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QWidget()
        bar.setFixedHeight(40)
        bar.setStyleSheet('background:#252526; border-bottom:1px solid #444;')
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 4, 8, 4)
        start_btn = QPushButton('▶  Start Measurement')
        start_btn.setStyleSheet('QPushButton{background:#1f7a1f;color:white;border-radius:3px;padding:3px 14px;} QPushButton:hover{background:#2a9a2a;}')
        start_btn.clicked.connect(self._start_measurement)
        bl.addWidget(start_btn)
        stop_btn = QPushButton('⏹  Stop Measurement')
        stop_btn.setStyleSheet('QPushButton{background:#7a1f1f;color:white;border-radius:3px;padding:3px 14px;} QPushButton:hover{background:#9a2a2a;}')
        stop_btn.clicked.connect(self._stop_measurement)
        bl.addWidget(stop_btn)
        pause_btn = QPushButton('⏸  Pause')
        pause_btn.clicked.connect(self._pause_measurement)
        bl.addWidget(pause_btn)
        reset_btn = QPushButton('↺  Reset')
        reset_btn.clicked.connect(self._reset_measurement)
        bl.addWidget(reset_btn)
        clear_btn = QPushButton('Clear Trace')
        clear_btn.clicked.connect(self._clear_trace)
        bl.addWidget(clear_btn)
        bl.addStretch()
        self.meas_indicator = QLabel('● Idle')
        self.meas_indicator.setStyleSheet('color:#888;font-weight:bold;')
        bl.addWidget(self.meas_indicator)
        outer.addWidget(bar)

        vsplit = QSplitter(Qt.Vertical)
        self.bus_canvas = CANBusGraphicsView()
        vsplit.addWidget(self.bus_canvas)

        bot = QTabWidget()
        bot.setStyleSheet('QTabBar::tab{padding:4px 12px;}')
        bot.addTab(self._make_write_panel(), 'Write')
        bot.addTab(self._make_editor_panel(), 'Editors')
        bot.addTab(self._make_script_panel(), 'Script')
        bot.addTab(self._make_uds_panel(), 'UDS')
        vsplit.addWidget(bot)
        vsplit.setSizes([420, 260])
        outer.addWidget(vsplit)

        self.main_tabs.addTab(tab, 'Simulation')
        self._init_simulation_nodes()

    def _init_simulation_nodes(self):
        self.bus_canvas.add_node('BCM', 180, 150)
        self.bus_canvas.add_node('Gateway', 420, 110)
        self.bus_canvas.add_node('Cluster', 640, 180)
        self.bus_canvas.add_node('Door Module', 880, 140)

    def _make_write_panel(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        grp = QGroupBox('Send CAN Message')
        gl = QVBoxLayout(grp)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel('ID (hex):'))
        self.write_id = QLineEdit('0x100')
        self.write_id.setMaximumWidth(90)
        r1.addWidget(self.write_id)
        r1.addWidget(QLabel('Owner:'))
        self.write_owner = QLineEdit('BCM')
        self.write_owner.setMaximumWidth(90)
        r1.addWidget(self.write_owner)
        r1.addWidget(QLabel('Data (hex):'))
        self.write_data = QLineEdit('01')
        r1.addWidget(self.write_data)
        r1.addWidget(QLabel('Cycle ms:'))
        self.cycle_time = QLineEdit('1000')
        self.cycle_time.setMaximumWidth(70)
        r1.addWidget(self.cycle_time)
        gl.addLayout(r1)
        r2 = QHBoxLayout()
        for lbl, fn in [('Send Once', self._send_message), ('Add Cyclic', self._add_cyclic_schedule), ('Stop Cyclic', self._stop_cyclic)]:
            b = QPushButton(lbl)
            b.clicked.connect(fn)
            r2.addWidget(b)
        r2.addStretch()
        gl.addLayout(r2)
        lay.addWidget(grp)

        scheduler_group = QGroupBox('Cyclic Message Engine')
        scheduler_layout = QVBoxLayout(scheduler_group)
        self.scheduler_table = QTableWidget(0, 5)
        self.scheduler_table.setHorizontalHeaderLabels(['Enable', 'Owner', 'Message ID', 'Cycle ms', 'State'])
        self.scheduler_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.scheduler_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        scheduler_layout.addWidget(self.scheduler_table)
        ctrl = QHBoxLayout()
        refresh_btn = QPushButton('Refresh')
        refresh_btn.clicked.connect(self._refresh_scheduler_table)
        ctrl.addWidget(refresh_btn)
        start_btn = QPushButton('Start/Enable')
        start_btn.clicked.connect(self._enable_selected_schedule)
        ctrl.addWidget(start_btn)
        stop_btn = QPushButton('Stop/Disable')
        stop_btn.clicked.connect(self._disable_selected_schedule)
        ctrl.addWidget(stop_btn)
        remove_btn = QPushButton('Remove')
        remove_btn.clicked.connect(self._remove_selected_schedule)
        ctrl.addWidget(remove_btn)
        ctrl.addStretch()
        scheduler_layout.addLayout(ctrl)
        lay.addWidget(scheduler_group)
        self._refresh_scheduler_table()
        return w

    def _make_editor_panel(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)

        self.message_catalog = getattr(self, 'message_catalog', MessageCatalog())

        message_group = QGroupBox('Message Catalog')
        message_layout = QVBoxLayout(message_group)
        self.catalog_table = QTableWidget(0, 4)
        self.catalog_table.setHorizontalHeaderLabels(['Frame ID', 'Name', 'DLC', 'Signals'])
        self.catalog_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.catalog_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.catalog_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        message_layout.addWidget(self.catalog_table)

        form = QHBoxLayout()
        form.addWidget(QLabel('ID:'))
        self.catalog_id = QLineEdit('0x200')
        self.catalog_id.setMaximumWidth(90)
        form.addWidget(self.catalog_id)
        form.addWidget(QLabel('Name:'))
        self.catalog_name = QLineEdit('Custom_Message')
        form.addWidget(self.catalog_name)
        form.addWidget(QLabel('DLC:'))
        self.catalog_length = QLineEdit('8')
        self.catalog_length.setMaximumWidth(55)
        form.addWidget(self.catalog_length)
        form.addWidget(QLabel('Cycle ms:'))
        self.catalog_cycle = QLineEdit('500')
        self.catalog_cycle.setMaximumWidth(70)
        form.addWidget(self.catalog_cycle)
        message_layout.addLayout(form)

        buttons = QHBoxLayout()
        for label, callback in [
            ('Add / Update', self._upsert_catalog_message),
            ('Remove', self._remove_catalog_message),
            ('Refresh', self._refresh_message_catalog_table),
            ('Load JSON', self._load_message_catalog),
            ('Save JSON', self._save_message_catalog),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        buttons.addStretch()
        message_layout.addLayout(buttons)
        lay.addWidget(message_group, 2)

        signal_group = QGroupBox('Signal Builder')
        signal_layout = QVBoxLayout(signal_group)
        sform = QHBoxLayout()
        sform.addWidget(QLabel('Signal:'))
        self.signal_name = QLineEdit('Signal_1')
        sform.addWidget(self.signal_name)
        sform.addWidget(QLabel('Start bit:'))
        self.signal_start = QLineEdit('0')
        self.signal_start.setMaximumWidth(50)
        sform.addWidget(self.signal_start)
        sform.addWidget(QLabel('Length:'))
        self.signal_length = QLineEdit('8')
        self.signal_length.setMaximumWidth(50)
        sform.addWidget(self.signal_length)
        sform.addWidget(QLabel('Default:'))
        self.signal_value = QLineEdit('0')
        self.signal_value.setMaximumWidth(60)
        sform.addWidget(self.signal_value)
        signal_layout.addLayout(sform)

        sbuttons = QHBoxLayout()
        for label, callback in [
            ('Add Signal', self._add_catalog_signal),
            ('Remove Signal', self._remove_catalog_signal),
            ('Send Message', self._send_catalog_message),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            sbuttons.addWidget(button)
        sbuttons.addStretch()
        signal_layout.addLayout(sbuttons)

        self.catalog_preview = QTextEdit()
        self.catalog_preview.setReadOnly(True)
        self.catalog_preview.setPlaceholderText('Select a message to preview its signal layout...')
        signal_layout.addWidget(self.catalog_preview)

        lay.addWidget(signal_group, 1)
        self.catalog_table.itemSelectionChanged.connect(self._sync_catalog_form)
        self._refresh_message_catalog_table()
        return w

    def _make_script_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(QLabel('Python Script  (vars: can_if, bcm, analyzer, scheduler, dbc, uds)'))
        self.script_editor = QTextEdit()
        self.script_editor.setPlainText('# Example script\n# print(bcm.get_status())\n')
        lay.addWidget(self.script_editor)
        r = QHBoxLayout()
        rb = QPushButton('Run')
        rb.clicked.connect(self._run_script)
        r.addWidget(rb)
        cb = QPushButton('Clear')
        cb.clicked.connect(self.script_editor.clear)
        r.addWidget(cb)
        r.addStretch()
        lay.addLayout(r)
        self.script_output = QTextEdit()
        self.script_output.setReadOnly(True)
        self.script_output.setMaximumHeight(75)
        self.script_output.setPlaceholderText('Output…')
        lay.addWidget(self.script_output)
        return w

    def _start_measurement(self):
        if not self.measurement_running:
            self.measurement_running = True
            if hasattr(self, '_start_rx_worker'):
                self._start_rx_worker()
            self._start_dbc_stimulation()
            self._refresh_scheduler_table()
            self.meas_indicator.setText('● Running')
            self.meas_indicator.setStyleSheet('color:#44dd44;font-weight:bold;')
            self.statusBar().showMessage('Measurement Running…')

    def _pause_measurement(self):
        if self.measurement_running:
            if self.rx_timer.isActive():
                self.rx_timer.stop()
                self.meas_indicator.setText('● Paused')
                self.meas_indicator.setStyleSheet('color:#f2c14e;font-weight:bold;')
                self.statusBar().showMessage('Measurement Paused')
            else:
                self.rx_timer.start(100)
                self.meas_indicator.setText('● Running')
                self.meas_indicator.setStyleSheet('color:#44dd44;font-weight:bold;')
                self.statusBar().showMessage('Measurement Running…')

    def _reset_measurement(self):
        self._stop_measurement()
        self._clear_trace()
        self._clear_graph()
        self._update_status_labels()
        self.statusBar().showMessage('Measurement Reset')

    def _stop_measurement(self):
        if self.measurement_running:
            self.measurement_running = False
            if hasattr(self, '_stop_rx_worker'):
                self._stop_rx_worker()
            self.scheduler.stop_all()
            self._refresh_scheduler_table()
            self.meas_indicator.setText('● Idle')
            self.meas_indicator.setStyleSheet('color:#888;font-weight:bold;')
            self.statusBar().showMessage('Measurement Stopped')

    def _send_message(self):
        try:
            id_val = int(self.write_id.text(), 16)
            raw = self.write_data.text().replace('0x', '').replace(',', ' ')
            data = bytes(int(x, 16) for x in raw.split())
            self.can_if.send_message(id_val, data)
            msg = type('M', (), {'arbitration_id': id_val, 'data': data, 'timestamp': time.time()})()
            self.bcm.process_message(msg)
            self._add_trace_message(msg, 'Tx')
            self.tx_count += 1
            self._update_status_labels()
            self.statusBar().showMessage(f'Sent 0x{id_val:03X}: {data.hex().upper()}')
        except Exception as e:
            QMessageBox.warning(self, 'Send Error', str(e))

    def _add_cyclic_schedule(self):
        try:
            aid = int(self.write_id.text(), 16)
            raw = self.write_data.text().replace('0x', '').replace(',', ' ')
            data = bytes(int(x, 16) for x in raw.split())
            ms = int(self.cycle_time.text())
            owner = self.write_owner.text().strip() or 'BCM'
            self.scheduler.add_task(aid, data, ms, tag='manual', on_send=self._on_cyclic_tx, owner=owner, enabled=True)
            self._refresh_scheduler_table()
            self.statusBar().showMessage(f'Cyclic 0x{aid:03X} every {ms} ms')
        except Exception as e:
            QMessageBox.warning(self, 'Schedule Error', str(e))

    def _stop_cyclic(self):
        try:
            aid = int(self.write_id.text(), 16)
            self.scheduler.remove_task(aid)
            self._refresh_scheduler_table()
            self.statusBar().showMessage(f'Stopped cyclic 0x{aid:03X}')
        except Exception as e:
            QMessageBox.warning(self, 'Stop Error', str(e))

    def _selected_catalog_frame_id(self):
        row = self.catalog_table.currentRow() if hasattr(self, 'catalog_table') else -1
        if row < 0:
            return None
        item = self.catalog_table.item(row, 0)
        return int(item.text(), 16) if item else None

    def _refresh_message_catalog_table(self):
        if not hasattr(self, 'catalog_table'):
            return
        rows = self.message_catalog.list_messages()
        self.catalog_table.setRowCount(len(rows))
        for row_index, message in enumerate(rows):
            values = [f'0x{message.frame_id:03X}', message.name, str(message.length), str(len(message.signals))]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.catalog_table.setItem(row_index, column, item)
        self._sync_catalog_form()

    def _sync_catalog_form(self):
        frame_id = self._selected_catalog_frame_id()
        if frame_id is None:
            self.catalog_preview.clear()
            return
        message = self.message_catalog.get_message(frame_id)
        if not message:
            self.catalog_preview.clear()
            return
        self.catalog_id.setText(f'0x{message.frame_id:03X}')
        self.catalog_name.setText(message.name)
        self.catalog_length.setText(str(message.length))
        self.catalog_cycle.setText(str(message.cycle_time))
        signal_lines = [f"{signal.name}: start={signal.start_bit}, len={signal.length}, default={signal.default_value}" for signal in message.signals]
        self.catalog_preview.setText('\n'.join(signal_lines) or 'No signals defined yet.')

    def _upsert_catalog_message(self):
        try:
            frame_id = int(self.catalog_id.text().strip(), 16)
            name = self.catalog_name.text().strip() or f'Msg_{frame_id:03X}'
            length = int(self.catalog_length.text().strip())
            cycle = int(self.catalog_cycle.text().strip() or '0')
            self.message_catalog.upsert_message(frame_id, name, length, cycle)
            self._refresh_message_catalog_table()
            self.statusBar().showMessage(f'Updated catalog message 0x{frame_id:03X}')
        except Exception as e:
            QMessageBox.warning(self, 'Message Editor', str(e))

    def _remove_catalog_message(self):
        frame_id = self._selected_catalog_frame_id()
        if frame_id is None:
            return
        self.message_catalog.remove_message(frame_id)
        self._refresh_message_catalog_table()
        self.catalog_preview.clear()

    def _add_catalog_signal(self):
        try:
            frame_id = self._selected_catalog_frame_id()
            if frame_id is None:
                raise ValueError('Select or create a message first')
            signal_name = self.signal_name.text().strip() or 'Signal'
            start_bit = int(self.signal_start.text().strip())
            length = int(self.signal_length.text().strip())
            default_value = int(self.signal_value.text().strip() or '0')
            self.message_catalog.add_signal(frame_id, signal_name, start_bit, length, default_value)
            self._refresh_message_catalog_table()
            self.statusBar().showMessage(f'Added signal {signal_name} to 0x{frame_id:03X}')
        except Exception as e:
            QMessageBox.warning(self, 'Signal Editor', str(e))

    def _remove_catalog_signal(self):
        frame_id = self._selected_catalog_frame_id()
        if frame_id is None:
            return
        signal_name = self.signal_name.text().strip()
        if not signal_name:
            return
        self.message_catalog.remove_signal(frame_id, signal_name)
        self._refresh_message_catalog_table()

    def _send_catalog_message(self):
        try:
            frame_id = self._selected_catalog_frame_id()
            if frame_id is None:
                raise ValueError('Select a catalog message first')
            message = self.message_catalog.get_message(frame_id)
            values = {signal.name: signal.default_value for signal in message.signals}
            payload = self.message_catalog.encode(frame_id, values)
            self.can_if.send_message(frame_id, payload)
            tx_msg = type('M', (), {'arbitration_id': frame_id, 'data': payload, 'timestamp': time.time()})()
            self.analyzer.log_message(tx_msg)
            self.bcm.process_message(tx_msg)
            self.tx_count += 1
            self._add_trace_message(tx_msg, 'Tx')
            self.statusBar().showMessage(f'Sent catalog message 0x{frame_id:03X}')
        except Exception as e:
            QMessageBox.warning(self, 'Send Catalog Message', str(e))

    def _load_message_catalog(self):
        fn, _ = QFileDialog.getOpenFileName(self, 'Load Message Catalog', '', 'JSON (*.json)')
        if not fn:
            return
        try:
            with open(fn, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.message_catalog.load_records(data.get('messages', data))
            self._refresh_message_catalog_table()
            self.statusBar().showMessage(f'Loaded message catalog: {fn}')
        except Exception as e:
            QMessageBox.warning(self, 'Load Catalog', str(e))

    def _save_message_catalog(self):
        fn, _ = QFileDialog.getSaveFileName(self, 'Save Message Catalog', 'message_catalog.json', 'JSON (*.json)')
        if not fn:
            return
        try:
            with open(fn, 'w', encoding='utf-8') as f:
                json.dump({'messages': self.message_catalog.to_records()}, f, indent=2)
            self.statusBar().showMessage(f'Saved message catalog: {fn}')
        except Exception as e:
            QMessageBox.warning(self, 'Save Catalog', str(e))

    def _refresh_scheduler_table(self):
        if not hasattr(self, 'scheduler_table'):
            return
        tasks = self.scheduler.list_tasks()
        self.scheduler_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            enable_item = QTableWidgetItem('Yes' if task.get('enabled', True) else 'No')
            enable_item.setFlags(enable_item.flags() & ~Qt.ItemIsEditable)
            self.scheduler_table.setItem(row, 0, enable_item)
            for col, key in enumerate(['owner', 'id', 'interval', 'state'], start=1):
                value = task.get(key, '')
                if key == 'id':
                    value = f"0x{value:03X}"
                elif key == 'interval':
                    value = str(value)
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.scheduler_table.setItem(row, col, item)

    def _selected_schedule_row(self):
        selected = self.scheduler_table.selectionModel().selectedRows() if hasattr(self, 'scheduler_table') and self.scheduler_table.selectionModel() else []
        return selected[0].row() if selected else -1

    def _enable_selected_schedule(self):
        row = self._selected_schedule_row()
        if row < 0:
            return
        msg_id = int(self.scheduler_table.item(row, 2).text(), 16)
        self.scheduler.set_task_enabled(msg_id, True)
        self._refresh_scheduler_table()

    def _disable_selected_schedule(self):
        row = self._selected_schedule_row()
        if row < 0:
            return
        msg_id = int(self.scheduler_table.item(row, 2).text(), 16)
        self.scheduler.set_task_enabled(msg_id, False)
        self._refresh_scheduler_table()

    def _remove_selected_schedule(self):
        row = self._selected_schedule_row()
        if row < 0:
            return
        msg_id = int(self.scheduler_table.item(row, 2).text(), 16)
        self.scheduler.remove_task(msg_id)
        self._refresh_scheduler_table()

    def _run_script(self):
        code = self.script_editor.toPlainText()
        ns = {'can_if': self.can_if, 'bcm': self.bcm, 'analyzer': self.analyzer, 'scheduler': self.scheduler, 'dbc': self.dbc, 'uds': self.uds}
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(code, {}, ns)
            self.script_output.setText(buf.getvalue() or 'Done (no output)')
            self.statusBar().showMessage('Script OK')
        except Exception as e:
            self.script_output.setText(f'Error: {e}')
            QMessageBox.warning(self, 'Script Error', str(e))
