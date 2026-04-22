import time

from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.simulation.bcm_model import BCM
from src.testing.reporting import build_test_report, render_html_report


class TestsTabMixin:
    def _build_test_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        hdr = QLabel('Test Setup')
        hdr.setStyleSheet('font-size:15px;font-weight:bold;color:#7ab8f5;')
        lay.addWidget(hdr)

        sp = QSplitter()

        left = QGroupBox('Test Cases')
        ll = QVBoxLayout(left)
        self.test_list = QTableWidget()
        self.test_list.setColumnCount(3)
        self.test_list.setHorizontalHeaderLabels(['Test Name', 'Status', 'Result'])
        tests = [
            ('BCM_Lights_On', 'Ready', '—'),
            ('BCM_Lights_Off', 'Ready', '—'),
            ('BCM_Doors_Lock', 'Ready', '—'),
            ('BCM_Doors_Unlock', 'Ready', '—'),
            ('BCM_Horn_On', 'Ready', '—'),
            ('BCM_Alarm_Activate', 'Ready', '—'),
            ('BCM_Left_Indicator', 'Ready', '—'),
            ('BCM_Right_Indicator', 'Ready', '—'),
            ('UDS_DiagSession', 'Ready', '—'),
            ('UDS_ECUReset', 'Ready', '—'),
            ('UDS_ReadDataByID', 'Ready', '—'),
        ]
        self.test_list.setRowCount(len(tests))
        for r, (n, s, res) in enumerate(tests):
            self.test_list.setItem(r, 0, QTableWidgetItem(n))
            self.test_list.setItem(r, 1, QTableWidgetItem(s))
            self.test_list.setItem(r, 2, QTableWidgetItem(res))
        ll.addWidget(self.test_list)
        br = QHBoxLayout()
        for lbl, fn in [
            ('Run All', self._run_all_tests),
            ('Run Selected', self._run_selected_test),
            ('Reset', self._reset_tests),
            ('Export JSON', lambda: self._export_test_report('json')),
            ('Export HTML', lambda: self._export_test_report('html')),
        ]:
            b = QPushButton(lbl)
            b.clicked.connect(fn)
            br.addWidget(b)
        ll.addLayout(br)
        self.test_summary = QLabel('Total: 0 | Pass: 0 | Fail: 0 | Error: 0')
        self.test_summary.setStyleSheet('color:#7ab8f5;font-weight:bold;')
        ll.addWidget(self.test_summary)
        sp.addWidget(left)

        right = QGroupBox('Test Log')
        rl = QVBoxLayout(right)
        self.test_log = QTextEdit()
        self.test_log.setReadOnly(True)
        rl.addWidget(self.test_log)
        cl = QPushButton('Clear')
        cl.setMaximumWidth(80)
        cl.clicked.connect(self.test_log.clear)
        rl.addWidget(cl)
        sp.addWidget(right)
        sp.setSizes([500, 380])
        lay.addWidget(sp)

        self.main_tabs.addTab(tab, 'Test Setup')
        self._update_test_summary()

    def _run_all_tests(self):
        self.test_log.clear()
        for r in range(self.test_list.rowCount()):
            self._exec_test(r)
        self._update_test_summary()

    def _run_selected_test(self):
        for r in set(i.row() for i in self.test_list.selectedItems()):
            self._exec_test(r)
        self._update_test_summary()

    def _exec_test(self, row):
        name = self.test_list.item(row, 0).text()
        self.test_list.setItem(row, 1, QTableWidgetItem('Running…'))
        QApplication.processEvents()
        try:
            ok = self._run_bcm_test(name)
            self.test_list.setItem(row, 1, QTableWidgetItem('Done'))
            self.test_list.setItem(row, 2, QTableWidgetItem('Pass ✅' if ok else 'Fail ❌'))
            self.test_log.append(f"[{'PASS' if ok else 'FAIL'}] {name}")
        except Exception as e:
            self.test_list.setItem(row, 1, QTableWidgetItem('Error'))
            self.test_list.setItem(row, 2, QTableWidgetItem('Error'))
            self.test_log.append(f'[ERROR] {name}: {e}')
        self._update_test_summary()

    def _run_bcm_test(self, name):
        M = lambda a, d: type('M', (), {'arbitration_id': a, 'data': d, 'timestamp': time.time()})()
        bcm = BCM()
        bcm.attach_uds(self.uds)
        tests = {
            'BCM_Lights_On': lambda: (bcm.process_message(M(0x100, b'\x01')), bcm.lights_on)[1],
            'BCM_Lights_Off': lambda: (bcm.process_message(M(0x100, b'\x00')), not bcm.lights_on)[1],
            'BCM_Doors_Lock': lambda: (bcm.process_message(M(0x101, b'\x01')), bcm.doors_locked)[1],
            'BCM_Doors_Unlock': lambda: (bcm.process_message(M(0x101, b'\x00')), not bcm.doors_locked)[1],
            'BCM_Horn_On': lambda: (bcm.process_message(M(0x103, b'\x01')), bcm.horn_on)[1],
            'BCM_Alarm_Activate': lambda: (bcm.process_message(M(0x105, b'\x01')), bcm.alarm_active)[1],
            'BCM_Left_Indicator': lambda: (bcm.process_message(M(0x106, b'\x01')), bcm.left_indicator)[1],
            'BCM_Right_Indicator': lambda: (bcm.process_message(M(0x107, b'\x01')), bcm.right_indicator)[1],
            'UDS_DiagSession': lambda: self.uds.send(0x10, b'\x01') == b'50 01',
            'UDS_ECUReset': lambda: self.uds.send(0x11, b'\x01') == b'51 01',
            'UDS_ReadDataByID': lambda: len(self.uds.send(0x22, b'\xf1\x90')) > 0,
        }
        fn = tests.get(name)
        return fn() if fn else False

    def _reset_tests(self):
        for r in range(self.test_list.rowCount()):
            self.test_list.setItem(r, 1, QTableWidgetItem('Ready'))
            self.test_list.setItem(r, 2, QTableWidgetItem('—'))
        self.test_log.clear()
        self._update_test_summary()

    def _collect_test_rows(self):
        rows = []
        for row in range(self.test_list.rowCount()):
            rows.append({
                'name': self.test_list.item(row, 0).text() if self.test_list.item(row, 0) else '',
                'status': self.test_list.item(row, 1).text() if self.test_list.item(row, 1) else '',
                'result': self.test_list.item(row, 2).text() if self.test_list.item(row, 2) else '',
            })
        return rows

    def _update_test_summary(self):
        if not hasattr(self, 'test_summary'):
            return
        report = build_test_report(self._collect_test_rows())
        summary = report['summary']
        self.test_summary.setText(
            f"Total: {summary['total']} | Pass: {summary['pass']} | Fail: {summary['fail']} | Error: {summary['error']}"
        )

    def _export_test_report(self, export_type='json'):
        rows = self._collect_test_rows()
        report = build_test_report(rows)
        if export_type == 'json':
            fn, _ = QFileDialog.getSaveFileName(self, 'Export Test Report', 'test_report.json', 'JSON (*.json)')
            if not fn:
                return
            import json

            with open(fn, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            self.statusBar().showMessage(f'Exported test report: {fn}')
        else:
            fn, _ = QFileDialog.getSaveFileName(self, 'Export Test Report', 'test_report.html', 'HTML (*.html)')
            if not fn:
                return
            with open(fn, 'w', encoding='utf-8') as f:
                f.write(render_html_report(report))
            self.statusBar().showMessage(f'Exported test report: {fn}')
