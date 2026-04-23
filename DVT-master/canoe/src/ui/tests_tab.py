import json
import time
import xml.etree.ElementTree as ET

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
from src.testing.reporting import build_test_report


class TestsTabMixin:
    def _build_test_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        hdr = QLabel('Test Setup')
        hdr.setStyleSheet('font-size:15px;font-weight:bold;color:#7ab8f5;')
        lay.addWidget(hdr)

        upload_layout = QHBoxLayout()
        self.load_file_btn = QPushButton('Load Test File')
        self.load_file_btn.clicked.connect(self._load_test_file)
        upload_layout.addWidget(self.load_file_btn)
        upload_layout.addStretch()
        lay.addLayout(upload_layout)

        sp = QSplitter()

        left = QGroupBox('Test Cases')
        ll = QVBoxLayout(left)
        self.test_list = QTableWidget()
        self.test_list.setColumnCount(4)
        self.test_list.setHorizontalHeaderLabels(['Test Name', 'Description', 'Status', 'Logs'])
        self._load_default_tests()
        ll.addWidget(self.test_list)
        br = QHBoxLayout()
        for lbl, fn in [
            ('Execute Tests', self._exec_tests),
        ]:
            b = QPushButton(lbl)
            b.clicked.connect(fn)
            br.addWidget(b)
        ll.addLayout(br)
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

    def _exec_tests(self):
        self.test_log.clear()
        for r in range(self.test_list.rowCount()):
            self._exec_test(r)

    def _run_selected_test(self):
        for r in set(i.row() for i in self.test_list.selectedItems()):
            self._exec_test(r)

    def _exec_test(self, row):
        name = self.test_list.item(row, 0).text()
        timestamp = time.strftime('%H:%M:%S')
        self.test_list.setItem(row, 2, QTableWidgetItem('Running…'))
        QApplication.processEvents()
        try:
            result = self._run_bcm_test(name)
            self.test_list.setItem(row, 2, QTableWidgetItem('Done'))
            self.test_list.setItem(row, 3, QTableWidgetItem(str(result)))
            self.test_log.append(f"[{timestamp}] Result: {result} for {name}")
        except Exception as e:
            self.test_list.setItem(row, 2, QTableWidgetItem('Error'))
            self.test_list.setItem(row, 3, QTableWidgetItem('Error'))
            self.test_log.append(f"[{timestamp}] [ERROR] {name}: {e}")

    def _run_bcm_test(self, name):
        M = lambda a, d: type('M', (), {'arbitration_id': a, 'data': d, 'timestamp': time.time()})()
        bcm = BCM()
        bcm.attach_uds(self.uds)
        # Map signal names and test names to BCM tests
        signal_mappings = {
            'light_state': 'BCM_Lights_On',
            'door_lock': 'BCM_Doors_Lock',
            'Headlight ON Command': 'BCM_Lights_On',
            'Headlight OFF Command': 'BCM_Lights_Off',
        }
        if name in signal_mappings:
            name = signal_mappings[name]
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
        return fn() if fn else f"Test '{name}' not implemented"

    def _reset_tests(self):
        for r in range(self.test_list.rowCount()):
            self.test_list.setItem(r, 2, QTableWidgetItem('Ready'))
            self.test_list.setItem(r, 3, QTableWidgetItem('—'))
        self.test_log.clear()

    def _collect_test_rows(self):
        rows = []
        for row in range(self.test_list.rowCount()):
            rows.append({
                'name': self.test_list.item(row, 0).text() if self.test_list.item(row, 0) else '',
                'description': self.test_list.item(row, 1).text() if self.test_list.item(row, 1) else '',
                'status': self.test_list.item(row, 2).text() if self.test_list.item(row, 2) else '',
                'result': self.test_list.item(row, 3).text() if self.test_list.item(row, 3) else '',
            })
        return rows

    def _load_default_tests(self):
        tests = [
            ('BCM_Lights_On', 'Test lights on', 'Ready', '—'),
            ('BCM_Lights_Off', 'Test lights off', 'Ready', '—'),
            ('BCM_Doors_Lock', 'Test doors lock', 'Ready', '—'),
            ('BCM_Doors_Unlock', 'Test doors unlock', 'Ready', '—'),
            ('BCM_Horn_On', 'Test horn on', 'Ready', '—'),
            ('BCM_Alarm_Activate', 'Test alarm activate', 'Ready', '—'),
            ('BCM_Left_Indicator', 'Test left indicator', 'Ready', '—'),
            ('BCM_Right_Indicator', 'Test right indicator', 'Ready', '—'),
            ('UDS_DiagSession', 'Test diagnostic session', 'Ready', '—'),
            ('UDS_ECUReset', 'Test ECU reset', 'Ready', '—'),
            ('UDS_ReadDataByID', 'Test read data by ID', 'Ready', '—'),
        ]
        self.test_list.setRowCount(len(tests))
        for r, (n, d, s, res) in enumerate(tests):
            self.test_list.setItem(r, 0, QTableWidgetItem(n))
            self.test_list.setItem(r, 1, QTableWidgetItem(d))
            self.test_list.setItem(r, 2, QTableWidgetItem(s))
            self.test_list.setItem(r, 3, QTableWidgetItem(res))

    def _load_test_file(self):
        fn, _ = QFileDialog.getOpenFileName(self, 'Load Test File', '', 'Test Files (*.json *.xml *.txt)')
        if not fn:
            return
        try:
            if fn.endswith('.json'):
                tests = self._parse_json(fn)
            elif fn.endswith('.xml'):
                tests = self._parse_xml(fn)
            elif fn.endswith('.txt'):
                tests = self._parse_txt(fn)
            else:
                raise ValueError('Unsupported file type')
            self.test_list.setRowCount(len(tests))
            for r, test in enumerate(tests):
                self.test_list.setItem(r, 0, QTableWidgetItem(test.get('name', '')))
                self.test_list.setItem(r, 1, QTableWidgetItem(test.get('description', '')))
                self.test_list.setItem(r, 2, QTableWidgetItem('Ready'))
                self.test_list.setItem(r, 3, QTableWidgetItem('—'))
            self.test_log.append(f'[{time.strftime("%H:%M:%S")}] Loaded {len(tests)} test cases from {fn}')
        except Exception as e:
            self.test_log.append(f'[{time.strftime("%H:%M:%S")}] Error loading file: {e}')

    def _parse_json(self, fn):
        with open(fn, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        elif 'messages' in data:
            # DBC-like format
            tests = []
            for msg_id, msg in data['messages'].items():
                for sig, info in msg['signals'].items():
                    tests.append({
                        'name': sig,
                        'description': f"Message {msg['name']} (ID {msg_id}), Signal {sig}, start_bit {info['start_bit']}, length {info['length']}"
                    })
            return tests
        elif 'test_cases' in data and isinstance(data['test_cases'], list):
            # Standard test cases format
            return data['test_cases']
        return []

    def _parse_xml(self, fn):
        tree = ET.parse(fn)
        root = tree.getroot()
        tests = []
        for test in root.findall('test'):
            tests.append({
                'name': test.find('name').text if test.find('name') is not None else '',
                'description': test.find('description').text if test.find('description') is not None else '',
            })
        return tests

    def _parse_txt(self, fn):
        with open(fn, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        tests = []
        for line in lines:
            line = line.strip()
            if line:
                parts = line.split('|', 1)
                name = parts[0].strip()
                desc = parts[1].strip() if len(parts) > 1 else ''
                tests.append({'name': name, 'description': desc})
        return tests

    def _update_test_summary(self):
        total = self.test_list.rowCount()
        pass_count = 0
        fail_count = 0
        error_count = 0
        for row in range(total):
            result_item = self.test_list.item(row, 3)
            if result_item:
                result = result_item.text()
                if 'Pass' in result:
                    pass_count += 1
                elif 'Fail' in result:
                    fail_count += 1
                elif 'Error' in result:
                    error_count += 1
        self.test_summary.setText(f'Total: {total} | Pass: {pass_count} | Fail: {fail_count} | Error: {error_count}')

