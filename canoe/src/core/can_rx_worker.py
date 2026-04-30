from PyQt5.QtCore import QThread, pyqtSignal


class CanRxWorker(QThread):
    message_received = pyqtSignal(object)
    worker_stopped = pyqtSignal()

    def __init__(self, can_manager, parent=None):
        super().__init__(parent)
        self.can_manager = can_manager
        self._running = True

    def run(self):
        while self._running:
            msg = self.can_manager.receive_message(0.1)
            if msg is not None:
                self.message_received.emit(msg)
            else:
                self.msleep(10)
        self.worker_stopped.emit()

    def stop(self):
        self._running = False