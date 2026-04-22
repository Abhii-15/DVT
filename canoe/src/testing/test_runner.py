from src.simulation.bcm_model import BCM


def run_basic_light_test():
    bcm = BCM()
    msg = type('M', (), {'arbitration_id': 0x100, 'data': b'\x01', 'timestamp': 0.0})()
    bcm.process_message(msg)
    return bcm.get_status().get('lights', False)
