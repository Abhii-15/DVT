from src.hil import HILInterface


class FailingBackend:
    backend_name = 'failing'

    def __init__(self, fail_on='send'):
        self.fail_on = fail_on
        self.connected = False

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def send(self, payload):
        if self.fail_on == 'send':
            raise RuntimeError('send failed')

    def receive(self, timeout=0.0):
        if self.fail_on == 'receive':
            raise RuntimeError('receive failed')
        return b'OK'

    def status(self):
        return {'backend': self.backend_name, 'connected': self.connected}


def test_virtual_connect_send_receive_disconnect():
    hil = HILInterface(tool='virtual')

    assert hil.connect() is True
    assert hil.is_connected() is True

    assert hil.send_to_hil(b'\x01\x02') is True
    received = hil.receive_from_hil()
    assert received == b'\x01\x02'

    state = hil.get_state()
    assert state['tx_count'] == 1
    assert state['rx_count'] == 1
    assert state['last_tx'] == b'\x01\x02'
    assert state['last_rx'] == b'\x01\x02'

    hil.disconnect()
    assert hil.is_connected() is False


def test_offline_send_and_receive_are_safe():
    hil = HILInterface(tool='virtual')

    assert hil.send_to_hil(b'\xAA') is False
    assert hil.receive_from_hil() is None

    state = hil.get_state()
    assert state['connected'] is False
    assert state['last_error'] == 'HIL is not connected'


def test_fallback_to_virtual_when_backend_unavailable():
    hil = HILInterface(tool='dspace', allow_fallback=True)

    assert hil.connect() is True
    state = hil.get_state()
    assert state['connected'] is True
    assert state['fallback_used'] is True
    assert state['backend'] == 'virtual'


def test_backend_send_failure_is_reported():
    hil = HILInterface(backend=FailingBackend(fail_on='send'), allow_fallback=False)

    assert hil.connect() is True
    assert hil.send_to_hil(b'\x10') is False
    assert hil.get_state()['last_error'] == 'send failed'


def test_backend_receive_failure_is_reported():
    hil = HILInterface(backend=FailingBackend(fail_on='receive'), allow_fallback=False)

    assert hil.connect() is True
    assert hil.receive_from_hil() is None
    assert hil.get_state()['last_error'] == 'receive failed'
