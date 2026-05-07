import json

import cantools


def _strip_unsupported_dbc_lines(raw_text):
    keep_lines = []
    drop_prefixes = (
        'BA_ ', 'BA_DEF_ ', 'BA_DEF_DEF_ ', 'BA_REL_ ', 'BA_DEF_REL_ ',
        'BA_DEF_DEF_REL_ ', 'VAL_ ', 'VAL_TABLE_ ', 'CM_ ', 'SG_MUL_VAL_',
    )
    for line in raw_text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(drop_prefixes):
            continue
        keep_lines.append(line)
    return '\n'.join(keep_lines)


def _fallback_parse_dbc_text(raw_text):
    import re

    message_re = re.compile(r'^\s*BO_\s+(\d+)\s+([A-Za-z0-9_]+)\s*:\s*(\d+)\s+(.+)$')
    signal_re = re.compile(r'^\s*SG_\s+([A-Za-z0-9_]+)\s*:\s*(\d+)\|(\d+)@([01])([+-])')

    messages = {}
    current_msg_id = None
    for line in raw_text.splitlines():
        msg_match = message_re.match(line)
        if msg_match:
            msg_id, name, length, _sender = msg_match.groups()
            current_msg_id = msg_id
            messages[msg_id] = {
                'name': name,
                'length': int(length),
                'signals': {},
            }
            continue

        sig_match = signal_re.match(line)
        if sig_match and current_msg_id and current_msg_id in messages:
            sig_name, start_bit, sig_length, byte_order, sign = sig_match.groups()
            messages[current_msg_id]['signals'][sig_name] = {
                'start_bit': int(start_bit),
                'length': int(sig_length),
                'byte_order': 'little_endian' if byte_order == '1' else 'big_endian',
                'is_signed': sign == '-',
            }

    return {
        'messages': messages,
    }


class DBCManager:
    def __init__(self):
        self.db = None

    def load(self, path):
        if path.endswith('.dbc'):
            try:
                self.db = cantools.database.load_file(path, strict=False)
            except Exception:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    raw_text = f.read()
                try:
                    self.db = cantools.database.load_string(_strip_unsupported_dbc_lines(raw_text), database_format='dbc', strict=False)
                except Exception:
                    self.db = self._fallback_to_runtime_db(_fallback_parse_dbc_text(raw_text))
            print(f'Loaded DBC file: {path}')
        elif path.endswith('.json'):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.db = self._json_to_db(data)
        else:
            raise ValueError('Unsupported DBC file format')

    def _json_to_db(self, data):
        db = cantools.database.Database()
        for msg_id, msg_data in data.get('messages', {}).items():
            msg = cantools.database.Message(
                frame_id=int(msg_id),
                name=msg_data.get('name', f'Msg_{msg_id}'),
                length=8,
                signals=[],
            )
            for sig_name, sig_info in msg_data.get('signals', {}).items():
                sig = cantools.database.Signal(
                    name=sig_name,
                    start=sig_info.get('start_bit', 0),
                    length=sig_info.get('length', 8),
                    byte_order='little_endian',
                    is_signed=False,
                )
                msg.signals.append(sig)
            db.messages.append(msg)
        return db

    def _fallback_to_runtime_db(self, data):
        db = cantools.database.Database()
        for msg_id, msg_data in data.get('messages', {}).items():
            msg = cantools.database.Message(
                frame_id=int(msg_id),
                name=msg_data.get('name', f'Msg_{msg_id}'),
                length=int(msg_data.get('length', 8)),
                signals=[],
            )
            for sig_name, sig_info in msg_data.get('signals', {}).items():
                sig = cantools.database.Signal(
                    name=sig_name,
                    start=sig_info.get('start_bit', 0),
                    length=sig_info.get('length', 8),
                    byte_order=sig_info.get('byte_order', 'little_endian'),
                    is_signed=sig_info.get('is_signed', False),
                )
                msg.signals.append(sig)
            db.messages.append(msg)
        return db

    def decode(self, msg):
        if not self.db:
            return {}
        try:
            return self.db.decode_message(msg.arbitration_id, msg.data)
        except Exception as e:
            print(f'Decode error: {e}')
            return {}

    def is_loaded(self):
        return self.db is not None

    def get_message_name(self, frame_id):
        if not self.db:
            return 'Unknown'
        try:
            msg = self.db.get_message_by_frame_id(frame_id)
            return msg.name
        except Exception:
            return f'0x{frame_id:X}'

    def get_messages(self):
        if not self.db:
            return []
        messages = []
        for msg in self.db.messages:
            messages.append({
                'id': msg.frame_id,
                'name': msg.name,
                'length': msg.length,
                'cycle_time': msg.cycle_time,
            })
        return messages

    def default_payload(self, frame_id):
        if not self.db:
            return bytes()
        try:
            msg = self.db.get_message_by_frame_id(frame_id)
        except Exception:
            return bytes()
        if msg.length <= 0:
            return bytes()
        return bytes([1] + [0] * (msg.length - 1))


# Backward-compatible class name used by existing code.
class DBC(DBCManager):
    pass
