import asyncio
import can


class CANManager:
    SUPPORTED_INTERFACES = ['virtual', 'pcan', 'vector', 'kvaser', 'socketcan']

    def __init__(self, channel='vcan0', bustype='virtual', bitrate=500, auto_connect=True):
        self.bus = None
        self.bustype = bustype
        self.channel = channel
        self.bitrate = bitrate
        self.connected = False
        self.fallback_used = False
        if auto_connect:
            self.connect()

    def _build_bus(self, channel, bustype, bitrate=None):
        bitrate = bitrate or self.bitrate
        kwargs = {
            'channel': channel,
            'bustype': bustype,
            'receive_own_messages': True,
        }
        if bustype in {'pcan', 'vector', 'kvaser', 'socketcan'} and bitrate:
            kwargs['bitrate'] = int(bitrate)
        try:
            return can.interface.Bus(**kwargs)
        except TypeError:
            kwargs.pop('receive_own_messages', None)
            kwargs.pop('bitrate', None)
            return can.interface.Bus(**kwargs)

    def connect(self, channel=None, bustype=None, bitrate=None, allow_fallback=True):
        if channel is not None:
            self.channel = channel
        if bustype is not None:
            self.bustype = bustype
        if bitrate is not None:
            self.bitrate = bitrate

        self.disconnect()
        self.fallback_used = False

        preferred_buses = [self.bustype] if self.bustype else []
        candidate_buses = []
        for bus_type in preferred_buses + ['pcan', 'vector', 'kvaser', 'socketcan', 'virtual']:
            if bus_type not in candidate_buses and bus_type in self.SUPPORTED_INTERFACES:
                candidate_buses.append(bus_type)

        for bus_type in candidate_buses:
            try:
                if bus_type == 'socketcan' and self.channel.startswith('vcan'):
                    continue
                self.bus = self._build_bus(self.channel, bus_type, self.bitrate)
                self.bustype = bus_type
                self.connected = True
                print(f'Connected to CAN bus: {bus_type} (channel={self.channel}, bitrate={self.bitrate})')
                return self
            except Exception as e:
                print(f'Failed to connect to {bus_type}: {e}')
                continue

        if allow_fallback:
            self.fallback_used = True
            try:
                self.bus = self._build_bus('test', 'virtual', self.bitrate)
                self.bustype = 'virtual'
                self.channel = 'test'
                self.connected = True
                print('Using virtual CAN bus')
                return self
            except Exception as e:
                raise RuntimeError(f'Could not initialize CAN bus: {e}')

        raise RuntimeError('Could not initialize CAN bus')

    def disconnect(self):
        if self.bus:
            try:
                self.bus.shutdown()
            finally:
                self.bus = None
        self.connected = False

    def is_connected(self):
        return self.connected and self.bus is not None

    def get_state(self):
        return {
            'connected': self.is_connected(),
            'interface': self.bustype,
            'channel': self.channel,
            'bitrate': self.bitrate,
            'fallback_used': self.fallback_used,
        }

    def send_message(self, arbitration_id, data):
        if not self.is_connected():
            raise RuntimeError('CAN bus is not connected')
        msg = can.Message(arbitration_id=arbitration_id, data=data, is_extended_id=False)
        self.bus.send(msg)
        print(f'Sent: {msg}')

    async def send_message_async(self, arbitration_id, data):
        if not self.is_connected():
            raise RuntimeError('CAN bus is not connected')
        msg = can.Message(arbitration_id=arbitration_id, data=data, is_extended_id=False)
        await asyncio.get_event_loop().run_in_executor(None, self.bus.send, msg)
        print(f'Sent async: {msg}')

    def receive_message(self, timeout=1.0):
        if not self.is_connected():
            return None
        msg = self.bus.recv(timeout=timeout)
        if msg:
            print(f'Received: {msg}')
        return msg

    async def receive_message_async(self, timeout=1.0):
        if not self.is_connected():
            return None
        loop = asyncio.get_event_loop()
        msg = await loop.run_in_executor(None, self.bus.recv, timeout)
        if msg:
            print(f'Received async: {msg}')
        return msg

    def close(self):
        self.disconnect()


# Backward-compatible class name used by existing code.
class CANInterface(CANManager):
    pass
