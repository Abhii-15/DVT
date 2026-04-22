class UDSService:
    def __init__(self):
        self.session_active = False
        self.security_level = 0
        self.data_records = {
            0xF190: b'1234567890',  # Example VIN
            0xF187: b'ECU123'       # Example ECU name
        }
        self.responses = {
            0x10: self._diagnostic_session_control,
            0x11: self._ecu_reset,
            0x22: self._read_data_by_identifier,
            0x27: self._security_access,
            0x2E: self._write_data_by_identifier,
            0x31: self._routine_control,
            0x34: self._request_download,
            0x36: self._transfer_data,
            0x37: self._request_transfer_exit
        }

    def send(self, service_id, data=b""):
        handler = self.responses.get(service_id, self._negative_response)
        return handler(data)

    def _diagnostic_session_control(self, data):
        subfunction = data[0] if data else 0x01
        if subfunction == 0x01:  # Default session
            self.session_active = True
            return b'50 01'
        return b'7F 10 12'  # Subfunction not supported

    def _ecu_reset(self, data):
        subfunction = data[0] if data else 0x01
        if subfunction == 0x01:  # Hard reset
            return b'51 01'
        return b'7F 11 12'

    def _read_data_by_identifier(self, data):
        if len(data) < 2:
            return b'7F 22 13'  # Incorrect message length
        did = int.from_bytes(data[:2], byteorder='big')
        record = self.data_records.get(did, b'')
        if record:
            return b'62' + data[:2] + record
        return b'7F 22 31'  # Request out of range

    def _write_data_by_identifier(self, data):
        if len(data) < 2:
            return b'7F 2E 13'
        did = int.from_bytes(data[:2], byteorder='big')
        if did in self.data_records:
            self.data_records[did] = data[2:]
            return b'6E' + data[:2]
        return b'7F 2E 31'

    def _security_access(self, data):
        subfunction = data[0] if data else 0x01
        if subfunction == 0x01:  # Request seed
            return b'67 01 12 34 56 78'  # Example seed
        elif subfunction == 0x02:  # Send key
            # Simple check: key == seed + 1
            if len(data) >= 5 and data[1:5] == b'\x13\x35\x57\x79':
                self.security_level = 1
                return b'67 02'
            return b'7F 27 35'  # Invalid key
        return b'7F 27 12'

    def _routine_control(self, data):
        # Placeholder for routine control
        return b'71' + data[:2] if len(data) >= 2 else b'7F 31 13'

    def _request_download(self, data):
        # Placeholder
        return b'74 20 0F FF 00'  # Example response

    def _transfer_data(self, data):
        # Placeholder
        return b'76' + data[:1] if data else b'7F 36 13'

    def _request_transfer_exit(self, data):
        return b'77'

    def _negative_response(self, data):
        return b'7F' + bytes([list(self.responses.keys())[0]]) + b'11'  # Service not supported

    def format_request(self, service_id, data=b""):
        return f"UDS 0x{service_id:02X} {data.hex().upper()}"

    def format_response(self, service_id):
        payload = self.send(service_id)
        return payload.hex().upper()