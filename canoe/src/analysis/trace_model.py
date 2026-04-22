from collections import deque

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt


class TraceTableModel(QAbstractTableModel):
    HEADERS = ['Timestamp', 'ID', 'Name', 'Direction', 'DLC', 'Raw Data', 'Decoded Signals']

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role not in (Qt.DisplayRole, Qt.ToolTipRole):
            return None
        row = self._rows[index.row()]
        key = self._column_key(index.column())
        return row.get(key, '')

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return str(section + 1)

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def clear(self):
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()

    def add_message(self, timestamp, arbitration_id, name, direction, data_bytes, decoded_signals=''):
        raw_data = ' '.join(f'{b:02X}' for b in data_bytes)
        row = {
            'Timestamp': f'{timestamp:.3f}',
            'ID': f'0x{arbitration_id:03X}',
            'Name': name or '',
            'Direction': direction,
            'DLC': str(len(data_bytes)),
            'Raw Data': raw_data,
            'Decoded Signals': decoded_signals or '',
        }
        self.beginInsertRows(QModelIndex(), len(self._rows), len(self._rows))
        self._rows.append(row)
        self.endInsertRows()

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def to_records(self):
        return list(self._rows)

    def get_row(self, row_index):
        return self._rows[row_index]

    def remove_all(self):
        self.clear()

    def _column_key(self, column):
        return self.HEADERS[column]


class TraceMetrics:
    def __init__(self, window_size=250):
        self.timestamps = deque(maxlen=window_size)
        self.ids = deque(maxlen=window_size)

    def add(self, timestamp, arbitration_id):
        self.timestamps.append(timestamp)
        self.ids.append(arbitration_id)

    def clear(self):
        self.timestamps.clear()
        self.ids.clear()

    def frequency_hz(self):
        if len(self.timestamps) < 2:
            return 0.0
        span = self.timestamps[-1] - self.timestamps[0]
        if span <= 0:
            return 0.0
        return max(0.0, (len(self.timestamps) - 1) / span)

    def bus_load_percent(self, bitrate_kbps=500, avg_bits_per_frame=128):
        if bitrate_kbps <= 0:
            return 0.0
        frames_per_sec = self.frequency_hz()
        bits_per_sec = bitrate_kbps * 1000
        load = (frames_per_sec * avg_bits_per_frame) / bits_per_sec * 100.0
        return max(0.0, min(load, 100.0))
