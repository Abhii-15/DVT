import cantools
import json

class DBC:
    def __init__(self):
        self.db = None

    def load(self, path):
        if path.endswith('.dbc'):
            self.db = cantools.database.load_file(path)
            print(f"Loaded DBC file: {path}")
        elif path.endswith('.json'):
            # Fallback to JSON for compatibility
            with open(path, 'r') as f:
                data = json.load(f)
            # Convert JSON to cantools format (simplified)
            self.db = self._json_to_db(data)
        else:
            raise ValueError("Unsupported DBC file format")

    def _json_to_db(self, data):
        # Simple conversion for JSON DBC
        db = cantools.database.Database()
        for msg_id, msg_data in data.get('messages', {}).items():
            msg = cantools.database.Message(
                frame_id=int(msg_id),
                name=msg_data.get('name', f'Msg_{msg_id}'),
                length=8,  # Assume 8 bytes
                signals=[]
            )
            for sig_name, sig_info in msg_data.get('signals', {}).items():
                sig = cantools.database.Signal(
                    name=sig_name,
                    start=sig_info.get('start_bit', 0),
                    length=sig_info.get('length', 8),
                    byte_order='little_endian',
                    is_signed=False
                )
                msg.signals.append(sig)
            db.messages.append(msg)
        return db

    def decode(self, msg):
        if not self.db:
            return {}
        try:
            decoded = self.db.decode_message(msg.arbitration_id, msg.data)
            return decoded
        except Exception as e:
            print(f"Decode error: {e}")
            return {}

    def is_loaded(self):
        return self.db is not None

    def get_message_name(self, frame_id):
        if not self.db:
            return "Unknown"
        try:
            msg = self.db.get_message_by_frame_id(frame_id)
            return msg.name
        except Exception:
            return f"0x{frame_id:X}"

    def get_messages(self):
        if not self.db:
            return []
        msgs = []
        for msg in self.db.messages:
            msgs.append({
                'id': msg.frame_id,
                'name': msg.name,
                'length': msg.length,
                'cycle_time': msg.cycle_time,
            })
        return msgs

    def default_payload(self, frame_id):
        if not self.db:
            return bytes()
        try:
            msg = self.db.get_message_by_frame_id(frame_id)
        except Exception:
            return bytes()
        # Use a deterministic non-zero first byte so the trace visibly changes.
        if msg.length <= 0:
            return bytes()
        return bytes([1] + [0] * (msg.length - 1))
