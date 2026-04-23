from src.bcm_model import BCM
from src.can_interface import CANInterface

def test_lights():
    bcm = BCM()
    can_if = CANInterface()  # Note: This will fail without real CAN, for simulation use virtual

    # Send command to turn lights on
    can_if.send_message(0x100, [1])
    msg = can_if.receive_message()  # In real setup, BCM would respond
    if msg:
        bcm.process_message(msg)

    assert bcm.get_status()['lights'] == True
    print("Lights test passed")

    can_if.close()

if __name__ == "__main__":
    test_lights()