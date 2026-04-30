class BCM:
    def __init__(self):
        self.lights_on = False
        self.doors_locked = True
        self.windows_up = True
        self.horn_on = False
        self.fuel_level = 100
        self.alarm_active = False
        self.left_indicator = False
        self.right_indicator = False
        self.udssvc = None

    def attach_uds(self, uds_service):
        self.udssvc = uds_service

    def process_message(self, msg):
        if msg.arbitration_id == 0x100:
            if msg.data[0] == 1:
                self.lights_on = True
                print('Lights turned on')
            else:
                self.lights_on = False
                print('Lights turned off')
        elif msg.arbitration_id == 0x101:
            if msg.data[0] == 1:
                self.doors_locked = True
                print('Doors locked')
            else:
                self.doors_locked = False
                print('Doors unlocked')
        elif msg.arbitration_id == 0x102:
            if msg.data[0] == 1:
                self.windows_up = True
                print('Windows up')
            else:
                self.windows_up = False
                print('Windows down')
        elif msg.arbitration_id == 0x103:
            if msg.data[0] == 1:
                self.horn_on = True
                print('Horn on')
            else:
                self.horn_on = False
                print('Horn off')
        elif msg.arbitration_id == 0x104:
            self.fuel_level = msg.data[0]
            print(f'Fuel level set to {self.fuel_level}')
        elif msg.arbitration_id == 0x105:
            if msg.data[0] == 1:
                self.alarm_active = True
                print('Alarm activated')
            else:
                self.alarm_active = False
                print('Alarm deactivated')
        elif msg.arbitration_id == 0x106:
            if msg.data[0] == 1:
                self.left_indicator = True
                print('Left indicator on')
            else:
                self.left_indicator = False
                print('Left indicator off')
        elif msg.arbitration_id == 0x107:
            if msg.data[0] == 1:
                self.right_indicator = True
                print('Right indicator on')
            else:
                self.right_indicator = False
                print('Right indicator off')
        elif msg.arbitration_id == 0x7DF and self.udssvc:
            service_id = msg.data[0]
            resp = self.udssvc.send(service_id)
            print(f'UDS response: {resp}')

    def get_status(self):
        return {
            'lights': self.lights_on,
            'doors_locked': self.doors_locked,
            'windows_up': self.windows_up,
            'horn_on': self.horn_on,
            'fuel_level': self.fuel_level,
            'alarm_active': self.alarm_active,
            'left_indicator': self.left_indicator,
            'right_indicator': self.right_indicator,
        }
