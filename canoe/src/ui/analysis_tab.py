from PyQt5.QtCore import QSortFilterProxyModel, Qt
from PyQt5.QtWidgets import QAbstractItemView, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QTableView, QTextEdit, QVBoxLayout, QWidget
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
        fr = QHBoxLayout()
        fr.addWidget(QLabel('Filter ID:'))
        self.filter_id = QLineEdit()
        self.filter_id.setPlaceholderText('e.g. 0x100')
        self.filter_id.setMaximumWidth(110)
        fr.addWidget(self.filter_id)
        ab = QPushButton('Apply')
        ab.clicked.connect(self._apply_filter)
        fr.addWidget(ab)
        fr.addStretch()
        cb = QPushButton('Clear')
        cb.clicked.connect(self._clear_trace)
        fr.addWidget(cb)
        eb = QPushButton('Export CSV')
        eb.clicked.connect(lambda: self._export_trace('csv'))
        fr.addWidget(eb)
        xl = QPushButton('Export HTML')
        xl.clicked.connect(lambda: self._export_trace('html'))
        fr.addWidget(xl)
        xj = QPushButton('Export JSON')
        xj.clicked.connect(lambda: self._export_trace('json'))
        fr.addWidget(xj)
        xx = QPushButton('Export XLSX')
        xx.clicked.connect(lambda: self._export_trace('xlsx'))
        fr.addWidget(xx)
        tl.addLayout(fr)

        self.trace_model = TraceTableModel(self)
        self.trace_filter = QSortFilterProxyModel(self)
        self.trace_filter.setSourceModel(self.trace_model)
        self.trace_filter.setFilterKeyColumn(1)
        self.trace_filter.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.trace_table = QTableView()
        self.trace_table.setModel(self.trace_filter)
        self.trace_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.trace_table.setAlternatingRowColors(False)
        self.trace_table.horizontalHeader().setStretchLastSection(True)
        self.trace_table.horizontalHeader().setDefaultSectionSize(140)
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
        except Exception as e:
            self.analysis_text.setText(f'Error: {e}')

    def _show_bcm_status(self):
        s = self.bcm.get_status()
        self.analysis_text.setText('BCM Status:\n' + '\n'.join(f'  {k}: {v}' for k, v in s.items()))

    def _apply_filter(self):
        text = self.filter_id.text().strip()
        self.trace_filter.setFilterFixedString(text)
        self.statusBar().showMessage('Filter updated')

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
        base_filters = {
            'csv': 'CSV (*.csv)',
            'html': 'HTML (*.html)',
            'json': 'JSON (*.json)',
            'xlsx': 'Excel (*.xlsx)',
        }
        ext = export_type.lower()
        fn, _ = QFileDialog.getSaveFileName(self, 'Export Trace', f'trace.{ext}', base_filters.get(ext, 'CSV (*.csv)'))
        if not fn:
            return
        try:
            records = self.trace_model.to_records()
            if ext == 'csv':
                import csv
                with open(fn, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=self.trace_model.HEADERS)
                    writer.writeheader()
                    writer.writerows(records)
            elif ext == 'json':
                import json
                with open(fn, 'w', encoding='utf-8') as f:
                    json.dump(records, f, indent=2)
            elif ext == 'html':
                import pandas as pd
                pd.DataFrame(records).to_html(fn, index=False)
            elif ext == 'xlsx':
                import pandas as pd
                pd.DataFrame(records).to_excel(fn, index=False)
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
