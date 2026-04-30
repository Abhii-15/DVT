from dataclasses import dataclass, field


@dataclass
class SignalDefinition:
    name: str
    start_bit: int
    length: int
    default_value: int = 0


@dataclass
class MessageDefinition:
    frame_id: int
    name: str
    length: int = 8
    cycle_time: int = 0
    signals: list = field(default_factory=list)


class MessageCatalog:
    def __init__(self):
        self.messages = {}

    def upsert_message(self, frame_id, name, length=8, cycle_time=0):
        frame_id = int(frame_id)
        message = self.messages.get(frame_id)
        if message is None:
            message = MessageDefinition(frame_id=frame_id, name=name, length=int(length), cycle_time=int(cycle_time))
            self.messages[frame_id] = message
        else:
            message.name = name
            message.length = int(length)
            message.cycle_time = int(cycle_time)
        return message

    def remove_message(self, frame_id):
        self.messages.pop(int(frame_id), None)

    def add_signal(self, frame_id, name, start_bit, length, default_value=0):
        message = self.messages[int(frame_id)]
        for idx, signal in enumerate(message.signals):
            if signal.name == name:
                message.signals[idx] = SignalDefinition(name=name, start_bit=int(start_bit), length=int(length), default_value=int(default_value))
                return message.signals[idx]
        signal = SignalDefinition(name=name, start_bit=int(start_bit), length=int(length), default_value=int(default_value))
        message.signals.append(signal)
        return signal

    def remove_signal(self, frame_id, name):
        message = self.messages.get(int(frame_id))
        if not message:
            return
        message.signals = [signal for signal in message.signals if signal.name != name]

    def list_messages(self):
        return [self.messages[key] for key in sorted(self.messages)]

    def get_message(self, frame_id):
        return self.messages.get(int(frame_id))

    def encode(self, frame_id, values=None):
        message = self.get_message(frame_id)
        if not message:
            raise KeyError(f'Unknown message 0x{int(frame_id):03X}')
        values = values or {}
        total_bits = message.length * 8
        raw_value = 0
        for signal in message.signals:
            bit_length = int(signal.length)
            if bit_length <= 0:
                continue
            bit_offset = int(signal.start_bit)
            if bit_offset + bit_length > total_bits:
                raise ValueError(f'Signal {signal.name} exceeds message length')
            value = int(values.get(signal.name, signal.default_value))
            if value < 0 or value >= (1 << bit_length):
                raise ValueError(f'Signal {signal.name} value out of range')
            raw_value |= value << bit_offset
        return raw_value.to_bytes(message.length, byteorder='little', signed=False)

    def decode(self, frame_id, payload):
        message = self.get_message(frame_id)
        if not message:
            return {}
        payload_value = int.from_bytes(bytes(payload), byteorder='little', signed=False)
        decoded = {}
        for signal in message.signals:
            mask = (1 << signal.length) - 1
            decoded[signal.name] = (payload_value >> signal.start_bit) & mask
        return decoded

    def to_records(self):
        rows = []
        for message in self.list_messages():
            rows.append({
                'frame_id': message.frame_id,
                'name': message.name,
                'length': message.length,
                'cycle_time': message.cycle_time,
                'signals': [signal.__dict__.copy() for signal in message.signals],
            })
        return rows

    def load_records(self, rows):
        self.messages.clear()
        for row in rows:
            message = self.upsert_message(row.get('frame_id', 0), row.get('name', 'Message'), row.get('length', 8), row.get('cycle_time', 0))
            message.signals = []
            for signal_row in row.get('signals', []):
                self.add_signal(message.frame_id, signal_row.get('name', 'Signal'), signal_row.get('start_bit', 0), signal_row.get('length', 1), signal_row.get('default_value', 0))