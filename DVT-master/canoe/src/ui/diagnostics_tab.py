import contextlib
import io

from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class DiagnosticsTabMixin:
    def _make_uds_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        grp = QGroupBox('UDS Request')
        gl = QHBoxLayout(grp)
        gl.addWidget(QLabel('SID (hex):'))
        self.uds_service_id = QLineEdit('10')
        self.uds_service_id.setMaximumWidth(55)
        gl.addWidget(self.uds_service_id)
        gl.addWidget(QLabel('Data:'))
        self.uds_data_input = QLineEdit()
        self.uds_data_input.setPlaceholderText('optional hex')
        gl.addWidget(self.uds_data_input)
        ub = QPushButton('Send UDS')
        ub.clicked.connect(self._send_uds_request)
        gl.addWidget(ub)
        gl.addStretch()
        lay.addWidget(grp)
        self.uds_response_view = QTextEdit()
        self.uds_response_view.setReadOnly(True)
        lay.addWidget(self.uds_response_view)
        cl = QPushButton('Clear')
        cl.setMaximumWidth(80)
        cl.clicked.connect(self.uds_response_view.clear)
        lay.addWidget(cl)

        console_group = QGroupBox('Diagnostics Script Console')
        console_layout = QVBoxLayout(console_group)
        self.diagnostics_script = QTextEdit()
        self.diagnostics_script.setPlainText('# Available variables: can_if, bcm, analyzer, scheduler, dbc, uds\n# print(uds.send(0x10, b"\x01"))\n')
        console_layout.addWidget(self.diagnostics_script)
        console_buttons = QHBoxLayout()
        run_button = QPushButton('Run Console Script')
        run_button.clicked.connect(self._run_diagnostics_script)
        console_buttons.addWidget(run_button)
        clear_button = QPushButton('Clear')
        clear_button.clicked.connect(self.diagnostics_script.clear)
        console_buttons.addWidget(clear_button)
        console_buttons.addStretch()
        console_layout.addLayout(console_buttons)
        self.diagnostics_output = QTextEdit()
        self.diagnostics_output.setReadOnly(True)
        self.diagnostics_output.setMaximumHeight(110)
        self.diagnostics_output.setPlaceholderText('Console output...')
        console_layout.addWidget(self.diagnostics_output)
        lay.addWidget(console_group)
        return w

    def _send_uds_request(self):
        try:
            sid = int(self.uds_service_id.text().strip(), 16)
            raw = self.uds_data_input.text().strip().replace(' ', '')
            data = bytes.fromhex(raw) if raw else b''
            resp = self.uds.send(sid, data)
            rhex = resp.hex().upper() if resp else 'None'
            self.uds_response_view.append(
                f"→ SID 0x{sid:02X}  Data: {data.hex().upper() or '—'}\n"
                f'← Response: {rhex}\n'
            )
            self.statusBar().showMessage(f'UDS 0x{sid:02X} sent')
        except Exception as e:
            QMessageBox.warning(self, 'UDS Error', str(e))

    def _run_diagnostics_script(self):
        code = self.diagnostics_script.toPlainText()
        ns = {'can_if': self.can_if, 'bcm': self.bcm, 'analyzer': self.analyzer, 'scheduler': self.scheduler, 'dbc': self.dbc, 'uds': self.uds}
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(code, {}, ns)
            self.diagnostics_output.setText(buf.getvalue() or 'Done (no output)')
            self.statusBar().showMessage('Diagnostics script OK')
        except Exception as e:
            self.diagnostics_output.setText(f'Error: {e}')
            QMessageBox.warning(self, 'Diagnostics Script Error', str(e))
