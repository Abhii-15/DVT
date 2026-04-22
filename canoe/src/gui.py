import sys
import time
import json
import io
import contextlib
import os

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QLabel,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QGroupBox,
    QTabWidget, QFileDialog, QMessageBox, QDockWidget, QSplitter,
    QAction, QToolBar, QStatusBar, QScrollArea,
    QSizePolicy, QAbstractItemView, QHeaderView, QComboBox
)
from PyQt5.QtCore import QTimer, Qt, QSettings, QSize
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QFont
import pyqtgraph as pg
from pyqtgraph import PlotWidget

from src.dbc import DBC
from src.scheduler import CyclicScheduler
from src.uds import UDSService
from src.bcm_model import BCM
from src.can_interface import CANInterface
from src.analyze import Analyzer


# ─────────────────────────────────────────────────────────────
#  Bus Canvas  — replicates the LUXOFT DVT simulation view
# ─────────────────────────────────────────────────────────────
class BusCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 420)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.nodes = [{'name': 'Gateway', 'x': 120, 'y': 55}]

    def add_node(self, name, x=None, y=None):
        x = x or (80 + len(self.nodes) * 170)
        y = y or 55
        self.nodes.append({'name': name, 'x': x, 'y': y})
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor('#1e1e1e'))

        bus_h  = int(h * 0.40)
        bus_l  = int(h * 0.65)
        margin = 50

        # CAN_H line (red)
        p.setPen(QPen(QColor('#cc3333'), 2))
        p.drawLine(margin, bus_h, w - 20, bus_h)
        p.setFont(QFont('Segoe UI', 9, QFont.Bold))
        p.setPen(QColor('#cc3333'))
        p.drawText(4, bus_h + 5, 'CAN_H')

        # CAN_L line (green)
        p.setPen(QPen(QColor('#33aa33'), 2))
        p.drawLine(margin, bus_l, w - 20, bus_l)
        p.setPen(QColor('#33aa33'))
        p.drawText(4, bus_l + 5, 'CAN_L')

        # Nodes
        for node in self.nodes:
            nx, ny = node['x'], node['y']
            bw, bh = 80, 34
            bx = nx - bw // 2

            p.setBrush(QBrush(QColor('#3a7bd5')))
            p.setPen(QPen(QColor('#5599ff'), 1))
            p.drawRoundedRect(bx, ny, bw, bh, 4, 4)

            p.setFont(QFont('Segoe UI', 9, QFont.Bold))
            p.setPen(QColor('white'))
            p.drawText(bx, ny, bw, bh, Qt.AlignCenter, node['name'])

            # Drop line to CAN_H bus
            p.setPen(QPen(QColor('#888888'), 1, Qt.DashLine))
            p.drawLine(nx, ny + bh, nx, bus_h)

        p.end()


# ─────────────────────────────────────────────────────────────
#  Main Window
# ─────────────────────────────────────────────────────────────
class CANoeLikeGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LUXOFT DVT (Qt v0.26)")
        self.setGeometry(80, 80, 1400, 820)
        self._apply_dark_theme()

        self.bcm       = BCM()
        self.can_if    = CANInterface()
        self.analyzer  = Analyzer()
        self.dbc       = DBC()
        self.scheduler = CyclicScheduler(self.can_if)
        self.uds       = UDSService()
        self.bcm.attach_uds(self.uds)

        self.times = []
        self.ids   = []
        self.measurement_running = False
        self.auto_stim_tag = 'dbc_auto'
        self.settings = QSettings('LuxoftDVT', 'BCMTool')

        self._init_ui()
        self.rx_timer = QTimer()
        self.rx_timer.timeout.connect(self._update_trace)
        self.statusBar().showMessage("Ready")
        self._restore_layout()

    # ══════════════════════════════════════════════════════════
    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2b2b2b; color: #d4d4d4;
                font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px;
            }
            QMenuBar { background-color: #1e1e1e; color: #d4d4d4; border-bottom: 1px solid #444; }
            QMenuBar::item:selected { background-color: #3a3a3a; }
            QMenu { background-color: #252526; color: #d4d4d4; border: 1px solid #555; }
            QMenu::item:selected { background-color: #094771; }
            QToolBar { background-color: #252526; border-bottom: 1px solid #3a3a3a; spacing: 0px; padding: 0px; }
            QTabWidget::pane { border: 1px solid #444; background-color: #2b2b2b; }
            QTabBar::tab { background-color: #2d2d2d; color: #aaa; padding: 5px 16px;
                           border: 1px solid #444; border-bottom: none; margin-right: 2px; }
            QTabBar::tab:selected { background-color: #094771; color: #fff; border-bottom: 2px solid #0e86d4; }
            QTabBar::tab:hover:!selected { background-color: #3a3a3a; color: #fff; }
            QTreeWidget { background-color: #252526; color: #d4d4d4; border: none; }
            QTreeWidget::item:selected { background-color: #094771; }
            QTreeWidget::item:hover    { background-color: #2a2d2e; }
            QTableWidget { background-color: #1e1e1e; color: #d4d4d4;
                           gridline-color: #3a3a3a; border: none; }
            QTableWidget::item:selected { background-color: #094771; }
            QHeaderView::section { background-color: #2d2d2d; color: #d4d4d4;
                                   padding: 4px; border: 1px solid #444; }
            QPushButton { background-color: #3a3a3a; color: #d4d4d4; border: 1px solid #555;
                          border-radius: 3px; padding: 4px 12px; }
            QPushButton:hover   { background-color: #4a4a4a; border-color: #777; }
            QPushButton:pressed { background-color: #094771; }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #1e1e1e; color: #d4d4d4;
                border: 1px solid #555; border-radius: 2px; padding: 2px 4px;
            }
            QLineEdit:focus, QTextEdit:focus { border-color: #0e86d4; }
            QGroupBox { border: 1px solid #555; border-radius: 4px; margin-top: 8px;
                        color: #aaa; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; padding: 0 4px; }
            QDockWidget::title { background-color: #2d2d2d; padding: 4px;
                                 border-bottom: 1px solid #444; color: #d4d4d4; }
            QStatusBar { background-color: #007acc; color: white; }
            QScrollBar:vertical   { background:#2b2b2b; width:10px; }
            QScrollBar:horizontal { background:#2b2b2b; height:10px; }
            QScrollBar::handle { background:#555; border-radius:4px; min-height:20px; }
            QScrollBar::handle:hover { background:#777; }
        """)

    # ══════════════════════════════════════════════════════════
    def _init_ui(self):
        self._build_menubar()
        self._build_toolbar()
        self._build_network_explorer_dock()
        self._build_central()
        self.statusBar()

    # ── Menu Bar ──────────────────────────────────────────────
    def _build_menubar(self):
        mb = self.menuBar()

        fm = mb.addMenu('File')
        fm.addAction('New Configuration',  self._new_configuration)
        fm.addAction('Open Configuration', self._open_configuration)
        fm.addAction('Save Configuration', self._save_configuration)
        fm.addSeparator()
        fm.addAction('Exit', self.close)

        em = mb.addMenu('Edit')
        em.addAction('Add Node',     self._add_node_dialog)
        em.addAction('Load DBC…',    self._load_dbc)
        em.addSeparator()
        em.addAction('Clear Trace',  lambda: self.trace_table.setRowCount(0))
        em.addAction('Clear Graph',  self._clear_graph)

        tm = mb.addMenu('Tools')
        tm.addAction('Send CAN Message', lambda: self._go_to(2))
        tm.addAction('UDS Diagnostics',  lambda: self._go_to(2))
        tm.addAction('Run Script',       self._run_script)
        tm.addSeparator()
        tm.addAction('Export Trace CSV', self._export_trace)

        hm = mb.addMenu('Help')
        hm.addAction('About', lambda: QMessageBox.information(
            self, 'About',
            'LUXOFT DVT (Qt v0.26)\nBCM CAN Testing Tool\nPython + PyQt5'
        ))

    # ── Toolbar  (Hardware Setup | Analysis | Simulation | Test Setup) ──
    def _build_toolbar(self):
        tb = self.addToolBar("Sections")
        tb.setObjectName("SectionToolBar")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setStyleSheet("""
            QToolBar { background:#252526; border-bottom:2px solid #007acc; padding:0; spacing:0; }
        """)

        labels = ["Hardware Setup", "Analysis", "Simulation", "Test Setup"]
        self._sec_btns = []
        for i, lbl in enumerate(labels):
            btn = QPushButton(lbl)
            btn.setCheckable(True)
            btn.setMinimumWidth(120)
            btn.setMinimumHeight(32)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent; color: #bbb;
                    border: none; border-bottom: 3px solid transparent;
                    padding: 4px 18px; font-size: 12px;
                }
                QPushButton:checked {
                    color: #fff; border-bottom: 3px solid #007acc; font-weight: bold;
                }
                QPushButton:hover:!checked { color: #fff; background: #333; }
            """)
            btn.clicked.connect(lambda _, idx=i: self._go_to(idx))
            tb.addWidget(btn)
            self._sec_btns.append(btn)

        self._sec_btns[0].setChecked(True)

    def _go_to(self, index):
        for i, b in enumerate(self._sec_btns):
            b.setChecked(i == index)
        self.main_tabs.setCurrentIndex(index)

    # ── Left Dock : Simulation Network Explorer ───────────────
    def _build_network_explorer_dock(self):
        dock = QDockWidget("Simulation Network Explorer", self)
        dock.setObjectName("NetExplDock")
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setMinimumWidth(210)
        dock.setMaximumWidth(290)

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(4, 4, 4, 4)

        self.network_tree = QTreeWidget()
        self.network_tree.setHeaderHidden(True)
        self.network_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.network_tree.customContextMenuRequested.connect(self._tree_ctx_menu)
        self._populate_tree()
        lay.addWidget(self.network_tree)

        hint = QLabel("Right-click here to add a network.")
        hint.setStyleSheet("color:#555; font-size:10px; padding:2px;")
        lay.addWidget(hint)

        dock.setWidget(panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def _populate_tree(self):
        self.network_tree.clear()
        for net_name in ["CAN Network", "CAN Network 2"]:
            net = QTreeWidgetItem(self.network_tree, [net_name])
            QTreeWidgetItem(net, ["Nodes"])
            dbc_item = QTreeWidgetItem(net, ["DBC (Gateway.dbc)"])
            QTreeWidgetItem(net, ["Channels"])
            if net_name == "CAN Network 2":
                self.network_tree.setCurrentItem(dbc_item)
        self.network_tree.expandAll()

    def _tree_ctx_menu(self, pos):
        from PyQt5.QtWidgets import QMenu
        m = QMenu(self)
        m.addAction("Add Network",    self._add_network)
        m.addAction("Add Node",       self._add_node_dialog)
        m.addAction("Load DBC File",  self._load_dbc)
        m.addSeparator()
        m.addAction("Remove Selected", lambda: (
            self.network_tree.currentItem().parent().removeChild(
                self.network_tree.currentItem())
            if self.network_tree.currentItem() and self.network_tree.currentItem().parent()
            else None
        ))
        m.exec_(self.network_tree.viewport().mapToGlobal(pos))

    # ── Central 4-tab area ────────────────────────────────────
    def _build_central(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        lay = QVBoxLayout(cw)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.main_tabs = QTabWidget()
        self.main_tabs.tabBar().hide()
        lay.addWidget(self.main_tabs)

        self._build_hw_tab()
        self._build_analysis_tab()
        self._build_simulation_tab()
        self._build_test_tab()

    # ══════════════════════════════════════════════════════════
    #  TAB 0 — Hardware Setup
    # ══════════════════════════════════════════════════════════
    def _build_hw_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(14, 14, 14, 14)

        hdr = QLabel("Hardware Setup")
        hdr.setStyleSheet("font-size:15px; font-weight:bold; color:#7ab8f5;")
        lay.addWidget(hdr)

        sp = QSplitter(Qt.Horizontal)

        # Left: interface
        left = QGroupBox("CAN Interface")
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel("Bus Type:"))
        self.hw_bustype = QComboBox()
        self.hw_bustype.addItems(["virtual", "socketcan", "pcan", "kvaser"])
        ll.addWidget(self.hw_bustype)
        ll.addWidget(QLabel("Channel:"))
        self.hw_channel = QLineEdit("test")
        ll.addWidget(self.hw_channel)
        ll.addWidget(QLabel("Baud Rate (kbps):"))
        self.hw_baud = QComboBox()
        self.hw_baud.addItems(["125", "250", "500", "1000"])
        self.hw_baud.setCurrentText("500")
        ll.addWidget(self.hw_baud)
        conn_btn = QPushButton("Connect Interface")
        conn_btn.clicked.connect(self._hw_connect)
        ll.addWidget(conn_btn)
        self.hw_status = QLabel("Status: Not connected")
        self.hw_status.setStyleSheet("color:#e07070;")
        ll.addWidget(self.hw_status)
        ll.addStretch()
        sp.addWidget(left)

        # Right: DBC + node
        right = QGroupBox("Network & DBC")
        rl = QVBoxLayout(right)
        rl.addWidget(QLabel("Loaded DBC:"))
        self.hw_dbc_label = QLabel("None")
        self.hw_dbc_label.setStyleSheet("color:#7ab8f5;")
        rl.addWidget(self.hw_dbc_label)
        QPushButton_dbc = QPushButton("Load DBC File…")
        QPushButton_dbc.clicked.connect(self._load_dbc)
        rl.addWidget(QPushButton_dbc)
        rl.addSpacing(10)
        rl.addWidget(QLabel("Add Node to Canvas:"))
        self.hw_node_name = QLineEdit()
        self.hw_node_name.setPlaceholderText("e.g. ECU_BCM")
        rl.addWidget(self.hw_node_name)
        add_n = QPushButton("Add Node")
        add_n.clicked.connect(self._add_node_from_hw)
        rl.addWidget(add_n)
        rl.addStretch()
        sp.addWidget(right)

        sp.setSizes([300, 400])
        lay.addWidget(sp)
        self.main_tabs.addTab(tab, "Hardware Setup")

    # ══════════════════════════════════════════════════════════
    #  TAB 1 — Analysis
    # ══════════════════════════════════════════════════════════
    def _build_analysis_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 0, 0, 0)

        sub = QTabWidget()

        # Trace
        tw = QWidget()
        tl = QVBoxLayout(tw)
        tl.setContentsMargins(6, 6, 6, 6)
        fr = QHBoxLayout()
        fr.addWidget(QLabel("Filter ID:"))
        self.filter_id = QLineEdit(); self.filter_id.setPlaceholderText("e.g. 0x100")
        self.filter_id.setMaximumWidth(110); fr.addWidget(self.filter_id)
        ab = QPushButton("Apply"); ab.clicked.connect(self._apply_filter); fr.addWidget(ab)
        fr.addStretch()
        cb = QPushButton("Clear"); cb.clicked.connect(lambda: self.trace_table.setRowCount(0)); fr.addWidget(cb)
        eb = QPushButton("Export CSV"); eb.clicked.connect(self._export_trace); fr.addWidget(eb)
        tl.addLayout(fr)
        self.trace_table = QTableWidget()
        self.trace_table.setColumnCount(6)
        self.trace_table.setHorizontalHeaderLabels(["Time","ID","Name","DLC","Data","Dir"])
        self.trace_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.trace_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.trace_table.setAlternatingRowColors(True)
        self.trace_table.setStyleSheet(
            "alternate-background-color:#252526; background-color:#1e1e1e;")
        tl.addWidget(self.trace_table)
        sub.addTab(tw, "📋 Trace")

        # Graph
        gw = QWidget()
        gl = QVBoxLayout(gw); gl.setContentsMargins(6,6,6,6)
        self.graph_widget = PlotWidget(title="CAN Bus Traffic")
        self.graph_widget.setBackground('#1e1e1e')
        self.graph_widget.setLabel('left',   'CAN ID',   color='#aaa')
        self.graph_widget.setLabel('bottom', 'Time (s)', color='#aaa')
        self.graph_widget.showGrid(x=True, y=True, alpha=0.25)
        self.series = self.graph_widget.plot([], [], pen=None, symbol='o',
                                             symbolBrush='#3a7bd5', symbolSize=6)
        gl.addWidget(self.graph_widget)
        clrg = QPushButton("Clear Graph"); clrg.setMaximumWidth(110)
        clrg.clicked.connect(self._clear_graph); gl.addWidget(clrg)
        sub.addTab(gw, "📈 Graph")

        # Summary
        sw = QWidget()
        sl = QVBoxLayout(sw); sl.setContentsMargins(6,6,6,6)
        self.analysis_text = QTextEdit(); self.analysis_text.setReadOnly(True)
        sl.addWidget(self.analysis_text)
        br = QHBoxLayout()
        ra = QPushButton("Run Analysis"); ra.clicked.connect(self._run_analysis); br.addWidget(ra)
        bs = QPushButton("BCM Status");   bs.clicked.connect(self._show_bcm_status); br.addWidget(bs)
        br.addStretch(); sl.addLayout(br)
        sub.addTab(sw, "📊 Summary")

        lay.addWidget(sub)
        self.main_tabs.addTab(tab, "Analysis")

    # ══════════════════════════════════════════════════════════
    #  TAB 2 — Simulation
    # ══════════════════════════════════════════════════════════
    def _build_simulation_tab(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)

        # Measurement control bar
        bar = QWidget(); bar.setFixedHeight(36)
        bar.setStyleSheet("background:#252526; border-bottom:1px solid #444;")
        bl = QHBoxLayout(bar); bl.setContentsMargins(8,2,8,2)
        start_btn = QPushButton("▶  Start Measurement")
        start_btn.setStyleSheet(
            "QPushButton{background:#1f7a1f;color:white;border-radius:3px;padding:3px 14px;}"
            "QPushButton:hover{background:#2a9a2a;}")
        start_btn.clicked.connect(self._start_measurement); bl.addWidget(start_btn)
        stop_btn = QPushButton("⏹  Stop Measurement")
        stop_btn.setStyleSheet(
            "QPushButton{background:#7a1f1f;color:white;border-radius:3px;padding:3px 14px;}"
            "QPushButton:hover{background:#9a2a2a;}")
        stop_btn.clicked.connect(self._stop_measurement); bl.addWidget(stop_btn)
        bl.addStretch()
        self.meas_indicator = QLabel("● Idle")
        self.meas_indicator.setStyleSheet("color:#888;font-weight:bold;"); bl.addWidget(self.meas_indicator)
        outer.addWidget(bar)

        vsplit = QSplitter(Qt.Vertical)

        # Canvas
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        self.bus_canvas = BusCanvas()
        scroll.setWidget(self.bus_canvas)
        scroll.setStyleSheet("background:#1e1e1e; border:none;")
        vsplit.addWidget(scroll)

        # Bottom panel
        bot = QTabWidget()
        bot.setStyleSheet("QTabBar::tab{padding:4px 12px;}")
        bot.addTab(self._make_write_panel(),  "✍️  Write")
        bot.addTab(self._make_script_panel(), "🐍  Script")
        bot.addTab(self._make_uds_panel(),    "🔧  UDS")
        vsplit.addWidget(bot)
        vsplit.setSizes([310, 270])
        outer.addWidget(vsplit)

        self.main_tabs.addTab(tab, "Simulation")

    def _make_write_panel(self):
        w = QWidget(); lay = QHBoxLayout(w); lay.setContentsMargins(8,8,8,8)
        grp = QGroupBox("Send CAN Message"); gl = QVBoxLayout(grp)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("ID (hex):")); self.write_id = QLineEdit("0x100")
        self.write_id.setMaximumWidth(90); r1.addWidget(self.write_id)
        r1.addWidget(QLabel("Data (hex):")); self.write_data = QLineEdit("01"); r1.addWidget(self.write_data)
        r1.addWidget(QLabel("Cycle ms:")); self.cycle_time = QLineEdit("1000")
        self.cycle_time.setMaximumWidth(70); r1.addWidget(self.cycle_time)
        gl.addLayout(r1)
        r2 = QHBoxLayout()
        for lbl, fn in [("Send Once", self._send_message),
                        ("Add Cyclic", self._add_cyclic_schedule),
                        ("Stop Cyclic", self._stop_cyclic)]:
            b = QPushButton(lbl); b.clicked.connect(fn); r2.addWidget(b)
        r2.addStretch(); gl.addLayout(r2)
        lay.addWidget(grp); return w

    def _make_script_panel(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(8,8,8,8)
        lay.addWidget(QLabel("Python Script  (vars: can_if, bcm, analyzer, scheduler, dbc, uds)"))
        self.script_editor = QTextEdit()
        self.script_editor.setPlainText(
            "# Example: turn on lights\n"
            "# msg = type('Msg',(),{'arbitration_id':0x100,'data':bytes([1]),'timestamp':0})()\n"
            "# bcm.process_message(msg)\n"
            "# print(bcm.get_status())\n")
        lay.addWidget(self.script_editor)
        r = QHBoxLayout()
        rb = QPushButton("▶ Run"); rb.clicked.connect(self._run_script); r.addWidget(rb)
        cb = QPushButton("Clear"); cb.clicked.connect(self.script_editor.clear); r.addWidget(cb)
        r.addStretch(); lay.addLayout(r)
        self.script_output = QTextEdit(); self.script_output.setReadOnly(True)
        self.script_output.setMaximumHeight(75)
        self.script_output.setPlaceholderText("Output…"); lay.addWidget(self.script_output)
        return w

    def _make_uds_panel(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(8,8,8,8)
        grp = QGroupBox("UDS Request"); gl = QHBoxLayout(grp)
        gl.addWidget(QLabel("SID (hex):")); self.uds_service_id = QLineEdit("10")
        self.uds_service_id.setMaximumWidth(55); gl.addWidget(self.uds_service_id)
        gl.addWidget(QLabel("Data:")); self.uds_data_input = QLineEdit()
        self.uds_data_input.setPlaceholderText("optional hex"); gl.addWidget(self.uds_data_input)
        ub = QPushButton("Send UDS"); ub.clicked.connect(self._send_uds_request); gl.addWidget(ub)
        gl.addStretch(); lay.addWidget(grp)
        self.uds_response_view = QTextEdit(); self.uds_response_view.setReadOnly(True)
        lay.addWidget(self.uds_response_view)
        cl = QPushButton("Clear"); cl.setMaximumWidth(80)
        cl.clicked.connect(self.uds_response_view.clear); lay.addWidget(cl)
        return w

    # ══════════════════════════════════════════════════════════
    #  TAB 3 — Test Setup
    # ══════════════════════════════════════════════════════════
    def _build_test_tab(self):
        tab = QWidget(); lay = QVBoxLayout(tab); lay.setContentsMargins(12,12,12,12)
        hdr = QLabel("Test Setup")
        hdr.setStyleSheet("font-size:15px;font-weight:bold;color:#7ab8f5;"); lay.addWidget(hdr)

        sp = QSplitter(Qt.Horizontal)

        left = QGroupBox("Test Cases"); ll = QVBoxLayout(left)
        self.test_list = QTableWidget(); self.test_list.setColumnCount(3)
        self.test_list.setHorizontalHeaderLabels(["Test Name","Status","Result"])
        self.test_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tests = [
            ("BCM_Lights_On","Ready","—"),("BCM_Lights_Off","Ready","—"),
            ("BCM_Doors_Lock","Ready","—"),("BCM_Doors_Unlock","Ready","—"),
            ("BCM_Horn_On","Ready","—"),("BCM_Alarm_Activate","Ready","—"),
            ("BCM_Left_Indicator","Ready","—"),("BCM_Right_Indicator","Ready","—"),
            ("UDS_DiagSession","Ready","—"),("UDS_ECUReset","Ready","—"),
            ("UDS_ReadDataByID","Ready","—"),
        ]
        self.test_list.setRowCount(len(tests))
        for r,(n,s,res) in enumerate(tests):
            self.test_list.setItem(r,0,QTableWidgetItem(n))
            self.test_list.setItem(r,1,QTableWidgetItem(s))
            self.test_list.setItem(r,2,QTableWidgetItem(res))
        ll.addWidget(self.test_list)
        br = QHBoxLayout()
        for lbl,fn in [("▶ Run All",self._run_all_tests),
                       ("Run Selected",self._run_selected_test),
                       ("Reset",self._reset_tests)]:
            b=QPushButton(lbl); b.clicked.connect(fn); br.addWidget(b)
        ll.addLayout(br); sp.addWidget(left)

        right = QGroupBox("Test Log"); rl = QVBoxLayout(right)
        self.test_log = QTextEdit(); self.test_log.setReadOnly(True)
        rl.addWidget(self.test_log)
        cl = QPushButton("Clear"); cl.setMaximumWidth(80)
        cl.clicked.connect(self.test_log.clear); rl.addWidget(cl)
        sp.addWidget(right); sp.setSizes([500,380]); lay.addWidget(sp)

        self.main_tabs.addTab(tab, "Test Setup")

    # ══════════════════════════════════════════════════════════
    #  MEASUREMENT
    # ══════════════════════════════════════════════════════════
    def _start_measurement(self):
        if not self.measurement_running:
            self.measurement_running = True
            self.rx_timer.start(100)
            self._start_dbc_stimulation()
            self.meas_indicator.setText("● Running")
            self.meas_indicator.setStyleSheet("color:#44dd44;font-weight:bold;")
            self.statusBar().showMessage("Measurement Running…")

    def _stop_measurement(self):
        if self.measurement_running:
            self.measurement_running = False
            self.rx_timer.stop()
            self.scheduler.stop_all()
            self.meas_indicator.setText("● Idle")
            self.meas_indicator.setStyleSheet("color:#888;font-weight:bold;")
            self.statusBar().showMessage("Measurement Stopped")

    def _update_trace(self):
        if not self.measurement_running:
            return
        try:
            msg = self.can_if.receive_message(0.01)
            if not msg:
                return
            ft = self.filter_id.text().strip()
            if ft:
                try:
                    if msg.arbitration_id != int(ft, 16): return
                except ValueError: pass
            decoded  = self.dbc.decode(msg)
            msg_name = self.dbc.get_message_name(msg.arbitration_id)
            sig_name = ','.join(f'{k}={v}' for k,v in decoded.items()) if decoded else msg_name
            r = self.trace_table.rowCount(); self.trace_table.insertRow(r)
            self.trace_table.setItem(r,0,QTableWidgetItem(f"{msg.timestamp:.3f}"))
            self.trace_table.setItem(r,1,QTableWidgetItem(f"0x{msg.arbitration_id:03X}"))
            self.trace_table.setItem(r,2,QTableWidgetItem(sig_name))
            self.trace_table.setItem(r,3,QTableWidgetItem(str(len(msg.data))))
            self.trace_table.setItem(r,4,QTableWidgetItem(' '.join(f'{b:02X}' for b in msg.data)))
            self.trace_table.setItem(r,5,QTableWidgetItem("Rx"))
            self.trace_table.scrollToBottom()
            self.analyzer.log_message(msg)
            self.times.append(msg.timestamp); self.ids.append(msg.arbitration_id)
            self.series.setData(self.times, self.ids)
            self.statusBar().showMessage(f"Rx → 0x{msg.arbitration_id:03X} | {sig_name}")
        except Exception as e:
            self.statusBar().showMessage(f"Receive error: {e}")

    def _start_dbc_stimulation(self):
        if not self.dbc.is_loaded():
            return
        self._stop_dbc_stimulation()
        for msg in self.dbc.get_messages():
            cycle = msg.get('cycle_time') or 500
            payload = self.dbc.default_payload(msg['id'])
            if payload is None:
                continue
            self.scheduler.add_task(
                msg['id'],
                payload,
                int(cycle),
                tag=self.auto_stim_tag,
                on_send=self._on_cyclic_tx,
            )
        self.statusBar().showMessage("DBC auto-stimulation active")

    def _stop_dbc_stimulation(self):
        self.scheduler.remove_tasks_by_tag(self.auto_stim_tag)

    def _on_cyclic_tx(self, arbitration_id, data, _tag=None):
        if not self.measurement_running:
            return
        r = self.trace_table.rowCount(); self.trace_table.insertRow(r)
        now = time.time()
        self.trace_table.setItem(r,0,QTableWidgetItem(f"{now:.3f}"))
        self.trace_table.setItem(r,1,QTableWidgetItem(f"0x{arbitration_id:03X}"))
        self.trace_table.setItem(r,2,QTableWidgetItem(self.dbc.get_message_name(arbitration_id)))
        self.trace_table.setItem(r,3,QTableWidgetItem(str(len(data))))
        self.trace_table.setItem(r,4,QTableWidgetItem(' '.join(f'{b:02X}' for b in data)))
        self.trace_table.setItem(r,5,QTableWidgetItem("Tx"))
        self.trace_table.scrollToBottom()
        tx_msg = type('M',(),{'arbitration_id':arbitration_id,'data':data,'timestamp':now})()
        self.analyzer.log_message(tx_msg)
        self.bcm.process_message(tx_msg)

    # ══════════════════════════════════════════════════════════
    #  ACTIONS
    # ══════════════════════════════════════════════════════════
    def _hw_connect(self):
        try:
            self.can_if.close()
            bt = self.hw_bustype.currentText()
            ch = self.hw_channel.text().strip() or 'test'
            self.can_if = CANInterface(channel=ch, bustype=bt)
            self.scheduler = CyclicScheduler(self.can_if)
            if self.measurement_running:
                self._start_dbc_stimulation()
            self.hw_status.setText(f"Status: Connected ({bt}/{ch})")
            self.hw_status.setStyleSheet("color:#44dd44;")
            self.statusBar().showMessage(f"Connected: {bt} on {ch}")
        except Exception as e:
            self.hw_status.setText(f"Status: Error — {e}")
            self.hw_status.setStyleSheet("color:#e07070;")
            QMessageBox.warning(self, "Connection Error", str(e))

    def _send_message(self):
        try:
            id_val = int(self.write_id.text(), 16)
            raw    = self.write_data.text().replace('0x','').replace(',',' ')
            data   = bytes(int(x,16) for x in raw.split())
            self.can_if.send_message(id_val, data)
            r = self.trace_table.rowCount(); self.trace_table.insertRow(r)
            self.trace_table.setItem(r,0,QTableWidgetItem(f"{time.time():.3f}"))
            self.trace_table.setItem(r,1,QTableWidgetItem(f"0x{id_val:03X}"))
            self.trace_table.setItem(r,2,QTableWidgetItem("Sent"))
            self.trace_table.setItem(r,3,QTableWidgetItem(str(len(data))))
            self.trace_table.setItem(r,4,QTableWidgetItem(' '.join(f'{b:02X}' for b in data)))
            self.trace_table.setItem(r,5,QTableWidgetItem("Tx"))
            self.trace_table.scrollToBottom()
            msg = type('M',(),{'arbitration_id':id_val,'data':data,'timestamp':time.time()})()
            self.bcm.process_message(msg)
            self.statusBar().showMessage(f"Sent 0x{id_val:03X}: {data.hex().upper()}")
        except Exception as e:
            QMessageBox.warning(self, "Send Error", str(e))

    def _add_cyclic_schedule(self):
        try:
            aid  = int(self.write_id.text(), 16)
            raw  = self.write_data.text().replace('0x','').replace(',',' ')
            data = bytes(int(x,16) for x in raw.split())
            ms   = int(self.cycle_time.text())
            self.scheduler.add_task(aid, data, ms, tag='manual', on_send=self._on_cyclic_tx)
            self.statusBar().showMessage(f"Cyclic 0x{aid:03X} every {ms} ms")
        except Exception as e:
            QMessageBox.warning(self, "Schedule Error", str(e))

    def _stop_cyclic(self):
        try:
            aid = int(self.write_id.text(), 16)
            self.scheduler.remove_task(aid)
            self.statusBar().showMessage(f"Stopped cyclic 0x{aid:03X}")
        except Exception as e:
            QMessageBox.warning(self, "Stop Error", str(e))

    def _load_dbc(self):
        fn, _ = QFileDialog.getOpenFileName(self, 'Load DBC', '', 'DBC/JSON (*.dbc *.json)')
        if fn:
            try:
                self.dbc.load(fn)
                self.hw_dbc_label.setText(os.path.basename(fn))
                if self.measurement_running:
                    self._start_dbc_stimulation()
                self.statusBar().showMessage(f"DBC loaded: {fn}")
            except Exception as e:
                QMessageBox.warning(self, "Load Failed", str(e))

    def _run_analysis(self):
        try: self.analysis_text.setText(str(self.analyzer.summary()))
        except Exception as e: self.analysis_text.setText(f"Error: {e}")

    def _show_bcm_status(self):
        s = self.bcm.get_status()
        self.analysis_text.setText("BCM Status:\n" + "\n".join(f"  {k}: {v}" for k,v in s.items()))

    def _apply_filter(self):
        self.statusBar().showMessage("Filter active — applies to new incoming messages")

    def _run_script(self):
        code = self.script_editor.toPlainText()
        ns   = {'can_if':self.can_if,'bcm':self.bcm,'analyzer':self.analyzer,
                'scheduler':self.scheduler,'dbc':self.dbc,'uds':self.uds}
        buf  = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(code, {}, ns)
            self.script_output.setText(buf.getvalue() or "✅ Done (no output)")
            self.statusBar().showMessage("Script OK")
        except Exception as e:
            self.script_output.setText(f"❌ {e}")
            QMessageBox.warning(self, "Script Error", str(e))

    def _send_uds_request(self):
        try:
            sid  = int(self.uds_service_id.text().strip(), 16)
            raw  = self.uds_data_input.text().strip().replace(' ','')
            data = bytes.fromhex(raw) if raw else b""
            resp = self.uds.send(sid, data)
            rhex = resp.hex().upper() if resp else "None"
            self.uds_response_view.append(
                f"→ SID 0x{sid:02X}  Data: {data.hex().upper() or '—'}\n"
                f"← Response: {rhex}\n")
            self.statusBar().showMessage(f"UDS 0x{sid:02X} sent")
        except Exception as e:
            QMessageBox.warning(self, "UDS Error", str(e))

    def _export_trace(self):
        fn, _ = QFileDialog.getSaveFileName(self,'Export Trace','trace.csv','CSV (*.csv)')
        if not fn: return
        try:
            with open(fn,'w',encoding='utf-8') as f:
                f.write('Time,ID,Name,DLC,Data,Direction\n')
                for r in range(self.trace_table.rowCount()):
                    vals=[self.trace_table.item(r,c).text()
                          if self.trace_table.item(r,c) else '' for c in range(6)]
                    f.write(','.join(vals)+'\n')
            self.statusBar().showMessage(f"Exported: {fn}")
        except Exception as e:
            self.statusBar().showMessage(f"Export failed: {e}")

    def _clear_graph(self):
        self.times.clear(); self.ids.clear(); self.series.setData([],[])

    # ── Network explorer helpers ──────────────────────────────
    def _add_network(self):
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self,'Add Network','Network name:')
        if ok and name:
            it = QTreeWidgetItem(self.network_tree, [name])
            QTreeWidgetItem(it,["Nodes"]); QTreeWidgetItem(it,["Channels"])
            self.network_tree.expandAll()

    def _add_node_dialog(self):
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self,'Add Node','Node name:')
        if ok and name:
            self.bus_canvas.add_node(name)
            self.statusBar().showMessage(f"Node '{name}' added")

    def _add_node_from_hw(self):
        name = self.hw_node_name.text().strip()
        if name:
            self.bus_canvas.add_node(name); self.hw_node_name.clear()
            self.statusBar().showMessage(f"Node '{name}' added")
        else:
            QMessageBox.information(self,"Add Node","Enter a node name first.")

    # ── Test runner ───────────────────────────────────────────
    def _run_all_tests(self):
        self.test_log.clear()
        for r in range(self.test_list.rowCount()): self._exec_test(r)

    def _run_selected_test(self):
        for r in set(i.row() for i in self.test_list.selectedItems()): self._exec_test(r)

    def _exec_test(self, row):
        name = self.test_list.item(row,0).text()
        self.test_list.setItem(row,1,QTableWidgetItem("Running…"))
        QApplication.processEvents()
        try:
            ok = self._run_bcm_test(name)
            self.test_list.setItem(row,1,QTableWidgetItem("Done"))
            self.test_list.setItem(row,2,QTableWidgetItem("Pass ✅" if ok else "Fail ❌"))
            self.test_log.append(f"[{'PASS' if ok else 'FAIL'}] {name}")
        except Exception as e:
            self.test_list.setItem(row,1,QTableWidgetItem("Error"))
            self.test_list.setItem(row,2,QTableWidgetItem(f"Error"))
            self.test_log.append(f"[ERROR] {name}: {e}")

    def _run_bcm_test(self, name):
        M = lambda a,d: type('M',(),{'arbitration_id':a,'data':d,'timestamp':time.time()})()
        bcm = BCM(); bcm.attach_uds(self.uds)
        T = {
            "BCM_Lights_On":       lambda:(bcm.process_message(M(0x100,b'\x01')),bcm.lights_on)[1],
            "BCM_Lights_Off":      lambda:(bcm.process_message(M(0x100,b'\x00')),not bcm.lights_on)[1],
            "BCM_Doors_Lock":      lambda:(bcm.process_message(M(0x101,b'\x01')),bcm.doors_locked)[1],
            "BCM_Doors_Unlock":    lambda:(bcm.process_message(M(0x101,b'\x00')),not bcm.doors_locked)[1],
            "BCM_Horn_On":         lambda:(bcm.process_message(M(0x103,b'\x01')),bcm.horn_on)[1],
            "BCM_Alarm_Activate":  lambda:(bcm.process_message(M(0x105,b'\x01')),bcm.alarm_active)[1],
            "BCM_Left_Indicator":  lambda:(bcm.process_message(M(0x106,b'\x01')),bcm.left_indicator)[1],
            "BCM_Right_Indicator": lambda:(bcm.process_message(M(0x107,b'\x01')),bcm.right_indicator)[1],
            "UDS_DiagSession":     lambda: self.uds.send(0x10,b'\x01')==b'50 01',
            "UDS_ECUReset":        lambda: self.uds.send(0x11,b'\x01')==b'51 01',
            "UDS_ReadDataByID":    lambda: len(self.uds.send(0x22,b'\xf1\x90'))>0,
        }
        fn = T.get(name)
        return fn() if fn else False

    def _reset_tests(self):
        for r in range(self.test_list.rowCount()):
            self.test_list.setItem(r,1,QTableWidgetItem("Ready"))
            self.test_list.setItem(r,2,QTableWidgetItem("—"))
        self.test_log.clear()

    # ── Config ────────────────────────────────────────────────
    def _new_configuration(self):
        self.trace_table.setRowCount(0); self._clear_graph()
        self.analysis_text.clear(); self.uds_response_view.clear()
        self._stop_dbc_stimulation()
        self.bcm = BCM(); self.bcm.attach_uds(self.uds)
        self.statusBar().showMessage("New configuration")

    def _open_configuration(self):
        fn,_ = QFileDialog.getOpenFileName(self,'Open Config','','JSON (*.json)')
        if fn:
            try:
                with open(fn,'r') as f: data=json.load(f)
                self.trace_table.setRowCount(0)
                for item in data.get('trace',[]):
                    r=self.trace_table.rowCount(); self.trace_table.insertRow(r)
                    for ci,k in enumerate(['time','id','name','dlc','data','dir']):
                        self.trace_table.setItem(r,ci,QTableWidgetItem(str(item.get(k,''))))
                self.statusBar().showMessage(f"Loaded: {fn}")
            except Exception as e: QMessageBox.warning(self,'Open Failed',str(e))

    def _save_configuration(self):
        fn,_=QFileDialog.getSaveFileName(self,'Save Config','','JSON (*.json)')
        if fn:
            try:
                rows=[]
                for r in range(self.trace_table.rowCount()):
                    rows.append({k: self.trace_table.item(r,i).text()
                                 if self.trace_table.item(r,i) else ''
                                 for i,k in enumerate(['time','id','name','dlc','data','dir'])})
                with open(fn,'w') as f: json.dump({'trace':rows},f,indent=2)
                self.statusBar().showMessage(f"Saved: {fn}")
            except Exception as e: QMessageBox.warning(self,'Save Failed',str(e))

    def _save_layout(self):
        self.settings.setValue('geometry',self.saveGeometry())
        self.settings.setValue('windowState',self.saveState())

    def _restore_layout(self):
        g=self.settings.value('geometry')
        if g: self.restoreGeometry(g)
        s=self.settings.value('windowState')
        if s: self.restoreState(s)

    def closeEvent(self, event):
        self.scheduler.stop_all(); self._save_layout(); self.can_if.close(); event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CANoeLikeGUI()
    window.show()
    sys.exit(app.exec_())