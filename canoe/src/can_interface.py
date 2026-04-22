import can
import time
import asyncio

class CANInterface:
    def __init__(self, channel='vcan0', bustype='virtual'):
        self.bus = None
        self.bustype = bustype
        self.channel = channel
        self._init_bus()

    def _init_bus(self):
        def _build_bus(channel, bustype):
            kwargs = {
                'channel': channel,
                'bustype': bustype,
                'receive_own_messages': True,
            }
            try:
                return can.interface.Bus(**kwargs)
            except TypeError:
                kwargs.pop('receive_own_messages', None)
                return can.interface.Bus(**kwargs)

        # Try hardware buses first
        preferred_buses = [self.bustype] if self.bustype else []
        hardware_buses = ['pcan', 'kvaser', 'socketcan']
        candidate_buses = []
        for bus_type in preferred_buses + hardware_buses + ['virtual']:
            if bus_type not in candidate_buses:
                candidate_buses.append(bus_type)

        for hw_type in candidate_buses:
            try:
                if hw_type == 'socketcan' and self.channel.startswith('vcan'):
                    continue  # Skip virtual for socketcan
                self.bus = _build_bus(self.channel, hw_type)
                print(f"Connected to CAN bus: {hw_type}")
                self.bustype = hw_type
                return
            except Exception as e:
                print(f"Failed to connect to {hw_type}: {e}")
                continue

        raise RuntimeError("Could not initialize CAN bus")

    def send_message(self, arbitration_id, data):
        msg = can.Message(arbitration_id=arbitration_id, data=data, is_extended_id=False)
        self.bus.send(msg)
        print(f"Sent: {msg}")

    async def send_message_async(self, arbitration_id, data):
        msg = can.Message(arbitration_id=arbitration_id, data=data, is_extended_id=False)
        await asyncio.get_event_loop().run_in_executor(None, self.bus.send, msg)
        print(f"Sent async: {msg}")

    def receive_message(self, timeout=1.0):
        msg = self.bus.recv(timeout=timeout)
        if msg:
            print(f"Received: {msg}")
        return msg

    async def receive_message_async(self, timeout=1.0):
        loop = asyncio.get_event_loop()
        msg = await loop.run_in_executor(None, self.bus.recv, timeout)
        if msg:
            print(f"Received async: {msg}")
        return msg

    def close(self):
        if self.bus:
            self.bus.shutdown()