import json
import logging
import os
import sys
import time

from PyQt5.QtCore import QSettings, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QDockWidget, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QPushButton, QSplashScreen, QStatusBar, QTabWidget, QTextEdit, QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from src.analysis.analyzer import Analyzer
from src.analysis.trace_model import TraceMetrics
from src.core.can_rx_worker import CanRxWorker
from src.core.state import RuntimeCounters
from src.can.can_manager import CANManager
from src.can import ChannelManager, DatabaseManager, Router
from src.diagnostics.dbc_manager import DBCManager
from src.diagnostics.uds_service import UDSService
from src.simulation.bcm_model import BCM
from src.simulation.scheduler import CyclicScheduler
from src.ui.analysis_tab import AnalysisTabMixin
from src.ui.diagnostics_tab import DiagnosticsTabMixin
from src.ui.hardware_tab import HardwareTabMixin
from src.ui.simulation_tab import SimulationTabMixin
from src.ui.tests_tab import TestsTabMixin
from src.ui.channel_mapping_panel import ChannelMappingPanel
from src.ui.channels_config_view import ChannelsConfigView


logger = logging.getLogger(__name__)


class CANoeLikeGUI(QMainWindow, HardwareTabMixin, AnalysisTabMixin, SimulationTabMixin, DiagnosticsTabMixin, TestsTabMixin):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('LUXOFT DVT - CANoe Style Workbench')
        self.setGeometry(70, 50, 1520, 900)
        self._apply_dark_theme()

        self.bcm = BCM()
        self.can_if = CANManager()
        self.analyzer = Analyzer()
        self.dbc = DBCManager()
        self.scheduler = CyclicScheduler(self.can_if)
        self.uds = UDSService()
        self.bcm.attach_uds(self.uds)
        
        # Channel Mapping System
        self.channel_manager = ChannelManager()
        self.database_manager = DatabaseManager()
        self.router = Router(self.channel_manager, self.database_manager)
        
        # Create default CAN channel
        self.default_channel = self.channel_manager.create_channel("CAN")
        self.router.rebuild_routing_map()

        self.times = []
        self.ids = []
        self.metrics = TraceMetrics()
        self.runtime = RuntimeCounters()
        self.measurement_running = False
        self.auto_stim_tag = 'dbc_auto'
        self.settings = QSettings('LuxoftDVT', 'BCMTool')
        self.tx_count = 0
        self.rx_count = 0
        self.rx_worker = None

        self._init_ui()
        self.rx_timer = QTimer()
        self.rx_timer.timeout.connect(self._update_trace)
        self._update_status_labels()
        self.statusBar().showMessage('Ready')
        self._restore_layout()

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #20242a; color: #d9dde3; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; }
            QMenuBar { background-color: #11161d; color: #d9dde3; border-bottom: 1px solid #2a3642; }
            QMenuBar::item { padding: 6px 10px; }
            QMenuBar::item:selected { background-color: #203247; }
            QMenu { background-color: #17202a; color: #d9dde3; border: 1px solid #2d3a46; }
            QMenu::item:selected { background-color: #274969; }
            QToolBar { background-color: #141b24; border-bottom: 1px solid #2a3642; spacing: 4px; padding: 2px; }
            QToolButton { background: #1d2935; border: 1px solid #2f4255; color: #d9dde3; padding: 4px 8px; border-radius: 3px; }
            QToolButton:hover { background: #27415a; }
            QTabWidget::pane { border: 1px solid #2a3642; background-color: #1a222c; }
            QTabBar::tab { background-color: #18212b; color: #9fb0c2; padding: 8px 14px; border: 1px solid #2b3948; margin-right: 2px; }
            QTabBar::tab:selected { color: #f2f6fb; background-color: #25486a; border-bottom: 2px solid #53b8ff; }
            QTreeWidget, QTableWidget, QTableView, QTextEdit { background-color: #121a22; color: #d9dde3; border: 1px solid #2a3642; gridline-color: #2d3b49; }
            QTableWidget::item, QTableView::item { background-color: #121a22; color: #d9dde3; }
            QTableWidget::item:selected, QTableView::item:selected { background-color: #25486a; color: #f2f6fb; }
            QTableWidget::item:alternate, QTableView::item:alternate { background-color: #121a22; }
            QHeaderView::section { background-color: #1a2530; color: #d9dde3; border: 1px solid #2a3642; padding: 4px; }
            QPushButton { background-color: #223242; color: #d9dde3; border: 1px solid #31506b; border-radius: 3px; padding: 4px 12px; }
            QPushButton:hover { background-color: #2c4660; }
            QLineEdit, QComboBox { background-color: #121a22; color: #d9dde3; border: 1px solid #38506a; border-radius: 2px; padding: 2px 4px; }
            QGroupBox { border: 1px solid #34475b; border-radius: 4px; margin-top: 8px; color: #afc2d6; font-weight: bold; }
            QStatusBar { background-color: #0f5f89; color: #f0f7ff; }
            QDockWidget::title { background-color: #17222e; border-bottom: 1px solid #2a3642; padding: 4px; color: #c8d7e6; }
        """)

    def _init_ui(self):
        self._build_menubar()
        self._build_primary_toolbar()
        self._build_section_toolbar()
        self._build_network_explorer_dock()
        self._build_log_dock()
        self._build_central()
        self.setStatusBar(QStatusBar(self))
        self._build_status_widgets()
        
        # Connect DBC upload panel signals (must be after _build_central which creates the panel)
        if hasattr(self, 'dbc_upload_panel'):
            self.dbc_upload_panel.dbc_file_selected.connect(self._on_dbc_file_selected)
            logger.info("DBC upload panel signal connected successfully")
        else:
            logger.warning("DBC upload panel not found during signal connection")

    def _build_menubar(self):
        mb = self.menuBar()
        fm = mb.addMenu('File')
        fm.addAction('New Configuration', self._new_configuration)
        fm.addAction('Open Configuration', self._open_configuration)
        fm.addAction('Save Configuration', self._save_configuration)
        fm.addSeparator()
        fm.addAction('Exit', self.close)
        em = mb.addMenu('Edit')
        em.addAction('Add Node', self._add_node_dialog)
        em.addAction('Load DBC…', self._load_dbc)
        em.addSeparator()
        em.addAction('Clear Trace', self._clear_trace)
        em.addAction('Clear Graph', self._clear_graph)
        tm = mb.addMenu('Tools')
        tm.addAction('Send CAN Message', lambda: self._go_to(2))
        tm.addAction('UDS Diagnostics', lambda: self._go_to(2))
        tm.addAction('Run Script', self._run_script)
        tm.addSeparator()
        tm.addAction('Export Trace CSV', lambda: self._export_trace('csv'))
        hm = mb.addMenu('Help')
        hm.addAction('About', lambda: QMessageBox.information(self, 'About', 'LUXOFT DVT\nProfessional CAN Simulation Workbench\nPython + PyQt5'))

    def _build_primary_toolbar(self):
        tb = QToolBar('Main Actions', self)
        tb.setObjectName('MainActionToolBar')
        tb.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, tb)
        for label, callback in [('New', self._new_configuration), ('Open', self._open_configuration), ('Save', self._save_configuration), ('Load DBC', self._load_dbc), ('Export', lambda: self._export_trace('csv'))]:
            action = tb.addAction(label)
            action.triggered.connect(callback)

    def _build_section_toolbar(self):
        self._sec_btns = []

    def _go_to(self, index):
        self.main_tabs.setCurrentIndex(index)

    def _build_network_explorer_dock(self):
        dock = QDockWidget('Simulation Network Explorer', self)
        dock.setObjectName('NetExplDock')
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setMinimumWidth(220)
        dock.setMaximumWidth(320)
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(4, 4, 4, 4)
        self.network_tree = QTreeWidget()
        self.network_tree.setHeaderHidden(True)
        self.network_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.network_tree.customContextMenuRequested.connect(self._tree_ctx_menu)
        self.network_tree.itemClicked.connect(self._on_network_item_clicked)
        self._populate_tree()
        lay.addWidget(self.network_tree)
        dock.setWidget(panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def _build_log_dock(self):
        self.log_dock = QDockWidget('Runtime Log', self)
        self.log_dock.setObjectName('RuntimeLogDock')
        self.log_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText('System runtime messages...')
        self.log_dock.setWidget(self.log_view)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)

    def _populate_tree(self):
        self.network_tree.clear()
        net = QTreeWidgetItem(self.network_tree, ['CAN Network'])
        nodes = QTreeWidgetItem(net, ['Nodes'])
        for node_name in ['BCM', 'Gateway', 'Cluster', 'Door Module']:
            QTreeWidgetItem(nodes, [node_name])
        QTreeWidgetItem(net, ['DBC (Gateway.dbc)'])
        QTreeWidgetItem(net, ['Channels'])
        self.network_tree.expandAll()

    def _on_network_item_clicked(self, item, column):
        name = item.text(0)
        if hasattr(self, 'bus_canvas') and name in getattr(self.bus_canvas, 'nodes', {}):
            self.bus_canvas.highlight_node(name)
            self.statusBar().showMessage(f'Highlighted node: {name}')

    def _tree_ctx_menu(self, pos):
        m = QMenu(self)
        m.addAction('Add Network', self._add_network)
        m.addAction('Add Node', self._add_node_dialog)
        m.addAction('Load DBC File', self._load_dbc)
        m.exec_(self.network_tree.viewport().mapToGlobal(pos))

    def _build_central(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        lay = QVBoxLayout(cw)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.main_tabs = QTabWidget()
        self.main_tabs.setDocumentMode(True)
        self.main_tabs.currentChanged.connect(self._sync_toolbar_to_tab)
        lay.addWidget(self.main_tabs)
        self._build_hw_tab()
        self._build_analysis_tab()
        self._build_simulation_tab()
        self._build_test_tab()

    def _build_status_widgets(self):
        self.status_can = QLabel('CAN: Offline')
        self.status_dbc = QLabel('DBC: None')
        self.status_rx = QLabel('RX: 0')
        self.status_tx = QLabel('TX: 0')
        self.status_active = QLabel('Active Cyclic: 0')
        for widget in [self.status_can, self.status_dbc, self.status_rx, self.status_tx, self.status_active]:
            self.statusBar().addPermanentWidget(widget)

    def _update_status_labels(self):
        state = self.can_if.get_state()
        self.runtime.tx_count = self.tx_count
        self.runtime.rx_count = self.rx_count
        self.runtime.active_cyclic_messages = len(self.scheduler.tasks)
        self.status_can.setText(f"CAN: {'Online' if state['connected'] else 'Offline'} {state['interface']}/{state['channel']} @ {state['bitrate']}")
        self.status_dbc.setText('DBC: Loaded' if self.dbc.is_loaded() else 'DBC: None')
        self.status_rx.setText(f'RX: {self.rx_count}')
        self.status_tx.setText(f'TX: {self.tx_count}')
        self.status_active.setText(f'Active Cyclic: {len(self.scheduler.tasks)}')

    def _sync_toolbar_to_tab(self, index):
        return

    def _log(self, text):
        self.log_view.append(f"[{time.strftime('%H:%M:%S')}] {text}")

    def _table_item(self, text):
        return QTableWidgetItem(text)

    def _add_trace_message(self, msg, direction):
        msg_name = self.dbc.get_message_name(msg.arbitration_id)
        decoded = self.dbc.decode(msg)
        decoded_signals = ', '.join(f'{k}={v}' for k, v in decoded.items()) if decoded else ''
        logger.debug(f"Adding trace: ID=0x{msg.arbitration_id:03X}, Name={msg_name}, Direction={direction}, Decoded={decoded_signals}")
        self.trace_model.add_message(msg.timestamp, msg.arbitration_id, msg_name, direction, msg.data, decoded_signals)
        self.times.append(msg.timestamp)
        self.ids.append(msg.arbitration_id)
        self.metrics.add(msg.timestamp, msg.arbitration_id)
        self.series.setData(self.times, self.ids)
        freq_points = list(range(1, len(self.times) + 1))
        freq_values = [self.metrics.frequency_hz()] * len(freq_points)
        self.freq_series.setData(freq_points, freq_values)
        self.graph_freq_label.setText(f'Frequency: {self.metrics.frequency_hz():.2f} Hz')
        self.graph_load_label.setText(f'Bus Load: {self.metrics.bus_load_percent(self.can_if.bitrate):.2f}%')
        self.graph_count_label.setText(f'Frames: {self.trace_model.rowCount()}')
        self._update_status_labels()

    def _update_trace(self):
        try:
            msg = self.can_if.receive_message(0.01)
            if msg:
                self._handle_received_message(msg)
        except Exception as e:
            self._log(f'Receive error: {e}')
            self.statusBar().showMessage(f'Receive error: {e}')

    def _handle_received_message(self, msg):
        if not self.measurement_running:
            return
        ft = self.filter_id.text().strip()
        if ft:
            try:
                if msg.arbitration_id != int(ft, 16):
                    return
            except ValueError:
                pass
        self.analyzer.log_message(msg)
        self.rx_count += 1
        self._add_trace_message(msg, 'Rx')
        self.statusBar().showMessage(f"Rx -> 0x{msg.arbitration_id:03X} | {self.dbc.get_message_name(msg.arbitration_id)}")

    def _start_rx_worker(self):
        if self.rx_worker and self.rx_worker.isRunning():
            return
        self.rx_worker = CanRxWorker(self.can_if, self)
        self.rx_worker.message_received.connect(self._handle_received_message)
        self.rx_worker.start()

    def _stop_rx_worker(self):
        if self.rx_worker:
            self.rx_worker.stop()
            self.rx_worker.wait(1500)
            self.rx_worker = None

    def _start_dbc_stimulation(self):
        logger.info(f"_start_dbc_stimulation called. DBC loaded: {self.dbc.is_loaded()}")
        if not self.dbc.is_loaded():
            logger.warning("DBC not loaded, cannot start stimulation")
            return
        self._stop_dbc_stimulation()
        messages = self.dbc.get_messages()
        logger.info(f"DBC has {len(messages)} messages to schedule")
        for msg in messages:
            logger.info(f"  Message: 0x{msg['id']:03X} = {msg['name']}")
            cycle = msg.get('cycle_time') or 500
            payload = self.dbc.default_payload(msg['id'])
            if payload is None:
                logger.warning(f"No payload for message 0x{msg['id']:03X}")
                continue
            logger.info(f"Adding scheduled task for 0x{msg['id']:03X} ({msg['name']}) every {cycle}ms")
            self.scheduler.add_task(msg['id'], payload, int(cycle), tag=self.auto_stim_tag, on_send=self._on_cyclic_tx)
        if hasattr(self, '_refresh_scheduler_table'):
            self._refresh_scheduler_table()
        self._update_status_labels()
        self._log('DBC auto stimulation activated')
        self.statusBar().showMessage('DBC auto-stimulation active')

    def _stop_dbc_stimulation(self):
        self.scheduler.remove_tasks_by_tag(self.auto_stim_tag)
        if hasattr(self, '_refresh_scheduler_table'):
            self._refresh_scheduler_table()
        self._update_status_labels()

    def _on_cyclic_tx(self, arbitration_id, data, _tag=None):
        logger.debug(f"_on_cyclic_tx called for 0x{arbitration_id:03X}")
        if not self.measurement_running:
            return
        now = time.time()
        tx_msg = type('M', (), {'arbitration_id': arbitration_id, 'data': data, 'timestamp': now})()
        self.analyzer.log_message(tx_msg)
        self.bcm.process_message(tx_msg)
        self.tx_count += 1
        self._add_trace_message(tx_msg, 'Tx')
        logger.debug(f"Message 0x{arbitration_id:03X} added to trace")

    def _load_dbc(self):
        fn, _ = QFileDialog.getOpenFileName(self, 'Load DBC', '', 'DBC/JSON (*.dbc *.json)')
        if fn:
            self._load_dbc_from_path(fn)

    def _on_dbc_file_selected(self, file_path: str):
        self._load_dbc_from_path(file_path)

    def _load_dbc_from_path(self, file_path: str):
        try:
            from pathlib import Path
            from src.ui.dbc_upload_panel import _parse_dbc_file, _parse_json_dbc

            path = Path(file_path)
            db_name = path.stem

            if path.suffix.lower() == '.json':
                db_dict, summary = _parse_json_dbc(path)
            else:
                db_dict, summary = _parse_dbc_file(path)

            messages = {}
            signals = {}
            for msg_id_str, msg_data in db_dict.get('messages', {}).items():
                try:
                    msg_id = int(msg_id_str)
                except (ValueError, TypeError):
                    continue
                messages[msg_id] = msg_data
                signals[msg_id] = msg_data.get('signals', {})

            self.database_manager.add_database(db_name, path, messages, signals)
            self.dbc.load(str(path))

            if hasattr(self, 'hw_dbc_label'):
                self.hw_dbc_label.setText(os.path.basename(str(path)))

            if self.measurement_running:
                self._start_dbc_stimulation()
            self._update_status_labels()

            if hasattr(self, 'channel_mapping_panel'):
                self.channel_mapping_panel.refresh_mappings()

            self._log(f'DBC loaded: {path} ({summary})')
            self.statusBar().showMessage(f'DBC loaded: {path}')
        except Exception as e:
            QMessageBox.warning(self, 'Load Failed', str(e))
            logger.exception('DBC load failed')

    def _add_network(self):
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, 'Add Network', 'Network name:')
        if ok and name:
            it = QTreeWidgetItem(self.network_tree, [name])
            QTreeWidgetItem(it, ['Nodes'])
            QTreeWidgetItem(it, ['Channels'])
            self.network_tree.expandAll()

    def _add_node_dialog(self):
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, 'Add Node', 'Node name:')
        if ok and name:
            self.bus_canvas.add_node(name)
            self.network_tree.expandAll()
            self.statusBar().showMessage(f"Node '{name}' added")

    def _new_configuration(self):
        self._clear_trace()
        self._clear_graph()
        self.analysis_text.clear()
        self.uds_response_view.clear()
        self._stop_dbc_stimulation()
        self.tx_count = 0
        self.rx_count = 0
        self.bcm = BCM()
        self.bcm.attach_uds(self.uds)
        self.metrics.clear()
        self._update_status_labels()
        self.statusBar().showMessage('New configuration')

    def _open_configuration(self):
        fn, _ = QFileDialog.getOpenFileName(self, 'Open Config', '', 'JSON (*.json)')
        if fn:
            try:
                with open(fn, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._clear_trace()
                for item in data.get('trace', []):
                    raw_hex = item.get('Raw Data', '') or item.get('data', '')
                    raw_bytes = bytes.fromhex(raw_hex.replace(' ', '')) if raw_hex else b''
                    self.trace_model.add_message(float(item.get('Timestamp', item.get('time', 0.0)) or 0.0), int(str(item.get('ID', item.get('id', '0'))).replace('0x', ''), 16), item.get('Name', item.get('name', '')), item.get('Direction', item.get('dir', '')), raw_bytes, item.get('Decoded Signals', ''))
                self._log(f'Configuration loaded: {fn}')
                self.statusBar().showMessage(f'Loaded: {fn}')
            except Exception as e:
                QMessageBox.warning(self, 'Open Failed', str(e))

    def _save_configuration(self):
        fn, _ = QFileDialog.getSaveFileName(self, 'Save Config', '', 'JSON (*.json)')
        if fn:
            try:
                with open(fn, 'w', encoding='utf-8') as f:
                    json.dump({'trace': self.trace_model.to_records()}, f, indent=2)
                self._log(f'Configuration saved: {fn}')
                self.statusBar().showMessage(f'Saved: {fn}')
            except Exception as e:
                QMessageBox.warning(self, 'Save Failed', str(e))

    def _save_layout(self):
        self.settings.setValue('geometry', self.saveGeometry())
        self.settings.setValue('windowState', self.saveState())

    def _restore_layout(self):
        g = self.settings.value('geometry')
        if g:
            self.restoreGeometry(g)
        s = self.settings.value('windowState')
        if s:
            self.restoreState(s)

    def closeEvent(self, event):
        self._stop_rx_worker()
        self.scheduler.stop_all()
        self._save_layout()
        self.can_if.close()
        event.accept()


def _create_splash():
    pix = QPixmap(760, 430)
    pix.fill(QColor('#0f1722'))
    painter = QPainter(pix)
    painter.setPen(QColor('#5cc8ff'))
    painter.drawRect(10, 10, 740, 410)
    painter.setPen(QColor('#d7ebff'))
    painter.setFont(QApplication.font())
    painter.drawText(36, 90, 'LUXOFT DVT')
    painter.drawText(36, 125, 'Professional CANoe-Style Bench')
    painter.setPen(QColor('#84a9c7'))
    painter.drawText(36, 168, 'Initializing modules...')
    painter.end()
    splash = QSplashScreen(pix)
    splash.setWindowFlags(splash.windowFlags() | Qt.WindowStaysOnTopHint)
    return splash


def _show_startup_sequence(app, splash):
    steps = ['Loading UI framework', 'Initializing CAN backend', 'Initializing DBC decoder', 'Initializing simulation runtime', 'Preparing diagnostics and scripting engine', 'Finalizing workspace']
    splash.show()
    for idx, msg in enumerate(steps, start=1):
        splash.showMessage(f'  {idx}/{len(steps)}  {msg}', Qt.AlignBottom | Qt.AlignLeft, QColor('#d7ebff'))
        app.processEvents()
        time.sleep(0.09)


def main():
    app = QApplication(sys.argv)
    splash = _create_splash()
    _show_startup_sequence(app, splash)
    window = CANoeLikeGUI()
    window.show()
    splash.finish(window)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
