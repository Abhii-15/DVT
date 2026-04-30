from PyQt5.QtCore import QSortFilterProxyModel, Qt, QTimer, QRegExp
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QTableView, QTextEdit, QVBoxLayout, QWidget
)
from pyqtgraph import PlotWidget

from src.analysis.trace_model import TraceMetrics, TraceTableModel


class AnalysisTabMixin:
    def _build_analysis_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 0, 0, 0)

        sub = QTabWidget()

        tw = QWidget()
        tl = QVBoxLayout(tw)
        tl.setContentsMargins(6, 6, 6, 6)
        
        # Top row: Analysis controls
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        top_row.setContentsMargins(0, 0, 0, 0)
        self.analysis_start_btn = QPushButton('Start Analysis')
        self.analysis_start_btn.clicked.connect(self._start_analysis)
        self.analysis_start_btn.setMaximumWidth(120)
        top_row.addWidget(self.analysis_start_btn)
        self.analysis_stop_btn = QPushButton('Stop Analysis')
        self.analysis_stop_btn.setEnabled(False)
        self.analysis_stop_btn.clicked.connect(self._stop_analysis)
        self.analysis_stop_btn.setMaximumWidth(120)
        top_row.addWidget(self.analysis_stop_btn)
        self.analysis_state_label = QLabel('Analysis: Idle')
        self.analysis_state_label.setStyleSheet('font-weight:bold; color:#7ab8f5;')
        top_row.addWidget(self.analysis_state_label)
        top_row.addStretch()
        cb = QPushButton('Clear')
        cb.clicked.connect(self._clear_trace)
        cb.setMaximumWidth(80)
        top_row.addWidget(cb)
        eb = QPushButton('Export CSV')
        eb.clicked.connect(lambda: self._export_trace('csv'))
        eb.setMaximumWidth(100)
        top_row.addWidget(eb)
        tl.addLayout(top_row)
        
        # Filter panel - horizontal layout for better usability
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        
        # Filter label
        filter_label = QLabel('Filters:')
        filter_label.setStyleSheet('font-weight:bold; color:#7ab8f5;')
        filter_layout.addWidget(filter_label)
        
        # ID filter
        filter_layout.addWidget(QLabel('Message ID:'))
        self.filter_id = QLineEdit()
        self.filter_id.setPlaceholderText('e.g. 0x100')
        self.filter_id.setMaximumWidth(120)
        self.filter_id.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.filter_id)
        
        # Name filter
        filter_layout.addWidget(QLabel('Name:'))
        self.filter_name = QLineEdit()
        self.filter_name.setPlaceholderText('e.g. Fuel_Info')
        self.filter_name.setMaximumWidth(140)
        self.filter_name.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.filter_name)
        
        # Direction filter
        filter_layout.addWidget(QLabel('Direction:'))
        self.filter_direction = QComboBox()
        self.filter_direction.addItems(['Any', 'Tx', 'Rx'])
        self.filter_direction.setMaximumWidth(90)
        self.filter_direction.currentTextChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.filter_direction)
        
        # Clear filters button
        clear_filters_btn = QPushButton('Clear Filters')
        clear_filters_btn.setMaximumWidth(100)
        clear_filters_btn.clicked.connect(self._clear_filters)
        filter_layout.addWidget(clear_filters_btn)
        
        filter_layout.addStretch()
        tl.addLayout(filter_layout)

        self.trace_analysis_label = QLabel('Analysis Output: Idle')
        self.trace_analysis_label.setStyleSheet('color:#7ab8f5; font-weight:bold;')
        tl.addWidget(self.trace_analysis_label)

        self.trace_model = TraceTableModel(self)
        self.trace_filter = QSortFilterProxyModel(self)
        self.trace_filter.setSourceModel(self.trace_model)
        self.trace_filter.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.trace_filter.setFilterKeyColumn(-1)

        self.trace_table = QTableView()
        self.trace_table.setModel(self.trace_filter)
        self.trace_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.trace_table.setAlternatingRowColors(False)
        self.trace_table.horizontalHeader().setStretchLastSection(True)
        self.trace_table.horizontalHeader().setDefaultSectionSize(140)
        self.trace_table.verticalHeader().setVisible(False)  # Hide index column
        tl.addWidget(self.trace_table)
        sub.addTab(tw, 'Trace')

        gw = QWidget()
        gl = QVBoxLayout(gw)
        gl.setContentsMargins(6, 6, 6, 6)

        stats_bar = QHBoxLayout()
        self.graph_freq_label = QLabel('Frequency: 0.0 Hz')
        self.graph_load_label = QLabel('Bus Load: 0.0%')
        self.graph_count_label = QLabel('Frames: 0')
        for lbl in [self.graph_freq_label, self.graph_load_label, self.graph_count_label]:
            lbl.setStyleSheet('color:#7ab8f5; font-weight:bold;')
            stats_bar.addWidget(lbl)
        stats_bar.addStretch()
        gl.addLayout(stats_bar)

        self.graph_widget = PlotWidget(title='CAN Bus Traffic')
        self.graph_widget.setBackground('#1e1e1e')
        self.graph_widget.setLabel('left', 'CAN ID', color='#aaa')
        self.graph_widget.setLabel('bottom', 'Time (s)', color='#aaa')
        self.graph_widget.showGrid(x=True, y=True, alpha=0.25)
        self.series = self.graph_widget.plot([], [], pen=None, symbol='o', symbolBrush='#3a7bd5', symbolSize=6)
        gl.addWidget(self.graph_widget)

        self.freq_widget = PlotWidget(title='Frame Frequency / Bus Load')
        self.freq_widget.setBackground('#1e1e1e')
        self.freq_widget.setLabel('left', 'Frequency (Hz)', color='#aaa')
        self.freq_widget.setLabel('bottom', 'Samples', color='#aaa')
        self.freq_widget.showGrid(x=True, y=True, alpha=0.25)
        self.freq_series = self.freq_widget.plot([], [], pen='#53b8ff')
        gl.addWidget(self.freq_widget)

        clrg = QPushButton('Clear Graph')
        clrg.setMaximumWidth(110)
        clrg.clicked.connect(self._clear_graph)
        gl.addWidget(clrg)
        sub.addTab(gw, 'Graph')

        sw = QWidget()
        sl = QVBoxLayout(sw)
        sl.setContentsMargins(6, 6, 6, 6)
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        sl.addWidget(self.analysis_text)
        br = QHBoxLayout()
        ra = QPushButton('Run Analysis')
        ra.clicked.connect(self._run_analysis)
        br.addWidget(ra)
        bs = QPushButton('BCM Status')
        bs.clicked.connect(self._show_bcm_status)
        br.addWidget(bs)
        br.addStretch()
        sl.addLayout(br)
        self.analysis_timer = QTimer(self)
        self.analysis_timer.setInterval(1000)
        self.analysis_timer.timeout.connect(self._run_analysis)
        self.analysis_running = False
        sub.addTab(sw, 'Summary')

        lay.addWidget(sub)
        self.main_tabs.addTab(tab, 'Analysis')
        self.metrics = TraceMetrics()

    def _run_analysis(self):
        try:
            df = self.analyzer.dataframe()
            summary = self.analyzer.summary()
            stats = [
                f'Frames logged: {len(df)}',
                f'Frame frequency: {self.analyzer.frame_frequency():.2f} Hz',
                f'Bus load estimate: {self.analyzer.bus_load_percent(getattr(self.can_if, "bitrate", 500)):.2f}%',
            ]
            self.analysis_text.setText('\n'.join(stats) + '\n\n' + str(summary))
            self.trace_analysis_label.setText(' | '.join(stats))
        except Exception as e:
            self.analysis_text.setText(f'Error: {e}')
            self.trace_analysis_label.setText(f'Analysis Error: {e}')

    def _start_analysis(self):
        if self.analysis_running:
            return
        self.analysis_timer.start()
        self.analysis_running = True
        self.analysis_start_btn.setEnabled(False)
        self.analysis_stop_btn.setEnabled(True)
        self.analysis_state_label.setText('Analysis: Running')
        self._run_analysis()
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage('Analysis started')

    def _stop_analysis(self):
        if not self.analysis_running:
            return
        self.analysis_timer.stop()
        self.analysis_running = False
        self.analysis_start_btn.setEnabled(True)
        self.analysis_stop_btn.setEnabled(False)
        self.analysis_state_label.setText('Analysis: Stopped')
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage('Analysis stopped')

    def _show_bcm_status(self):
        s = self.bcm.get_status()
        self.analysis_text.setText('BCM Status:\n' + '\n'.join(f'  {k}: {v}' for k, v in s.items()))

    def _apply_filter(self):
        """Apply multi-column filters based on ID, Name, and Direction."""
        id_text = self.filter_id.text().strip()
        name_text = self.filter_name.text().strip()
        direction_text = self.filter_direction.currentText()
        
        # Build combined filter pattern
        filter_patterns = []
        
        if id_text:
            # Match both hex and decimal formats
            try:
                if id_text.startswith('0x') or id_text.startswith('0X'):
                    id_num = int(id_text, 16)
                else:
                    id_num = int(id_text, 10)
                filter_patterns.append(f"0x{id_num:X}|{id_num}")
            except (ValueError, AttributeError):
                filter_patterns.append(id_text)
        
        if name_text:
            filter_patterns.append(name_text)
        
        if direction_text != 'Any':
            filter_patterns.append(f"\\b{direction_text}\\b")
        
        # Combine all patterns with OR logic
        if filter_patterns:
            combined_pattern = "|".join(f"({p})" for p in filter_patterns)
            regex = QRegExp(combined_pattern, Qt.CaseInsensitive)
            self.trace_filter.setFilterRegExp(regex)
        else:
            self.trace_filter.setFilterFixedString("")
        
        # Update status message
        active_filters = []
        if id_text:
            active_filters.append(f"ID: {id_text}")
        if name_text:
            active_filters.append(f"Name: {name_text}")
        if direction_text != 'Any':
            active_filters.append(f"Dir: {direction_text}")
        
        status = "Filters: " + ", ".join(active_filters) if active_filters else "No active filters"
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(status)
    
    def _clear_filters(self):
        """Clear all active filters."""
        self.filter_id.clear()
        self.filter_name.clear()
        self.filter_direction.setCurrentIndex(0)
        self._apply_filter()

    def _clear_trace(self):
        self.trace_model.clear()
        self.times.clear()
        self.ids.clear()
        self.metrics.clear()
        self.series.setData([], [])
        self.freq_series.setData([], [])
        self.graph_freq_label.setText('Frequency: 0.0 Hz')
        self.graph_load_label.setText('Bus Load: 0.0%')
        self.graph_count_label.setText('Frames: 0')

    def _export_trace(self, export_type='csv'):
        fn, _ = QFileDialog.getSaveFileName(self, 'Export Trace', 'trace.csv', 'CSV (*.csv)')
        if not fn:
            return
        try:
            records = self.trace_model.to_records()
            import csv
            with open(fn, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.trace_model.HEADERS)
                writer.writeheader()
                writer.writerows(records)
            self.statusBar().showMessage(f'Exported: {fn}')
        except Exception as e:
            self.statusBar().showMessage(f'Export failed: {e}')

    def _clear_graph(self):
        self.times.clear()
        self.ids.clear()
        if hasattr(self, 'metrics'):
            self.metrics.clear()
        self.series.setData([], [])
        self.freq_series.setData([], [])
        self.graph_freq_label.setText('Frequency: 0.0 Hz')
        self.graph_load_label.setText('Bus Load: 0.0%')
        self.graph_count_label.setText('Frames: 0')
