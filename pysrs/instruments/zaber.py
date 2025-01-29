import numpy as np
from zaber_motion import Units
from zaber_motion.ascii import Connection

class Zaber:
    def __init__(self, config=None, **kwargs):
        defaults = {
            'serial': 'COM3', 
            'num_shifts': 50,  
            'shift_size': 10,  # mm
            'shift_offset': 1,  # mm
        }

        if config:
            defaults.update(config)
        defaults.update(kwargs)

        for key, val in defaults.items():
            setattr(self, key, val)

    def scan_range(self):
        with Connection.open_serial_port(self.serial) as connection:
            connection.enable_alerts()
            devices = connection.detect_devices()

            if len(devices) == 0:
                print("No Zaber devices found.")
                return
            
            device = devices[0]
            axis = device.get_axis(1)

            print(f"Connected to Zaber device: {device}")

            if not axis.is_homed():
                print("Homing the stage...")
                axis.home()

            start_pos = self.shift_offset
            step_size = self.shift_size
            num_steps = self.num_shifts

            print(f"Starting scan at {start_pos} mm, moving {num_steps} steps with {step_size} mm per step.")

            for i in range(num_steps):
                pos = start_pos + i * step_size
                print(f"Moving to {pos} mm")
                axis.move_absolute(pos, Units.LENGTH_MILLIMETRES)
                axis.wait_until_idle()


if __name__ == '__main__':
    config = {
        'serial': 'COM3', 
        'num_shifts': 3,  
        'shift_size': 5,  # mm
        'shift_offset': 20,  # mm
    }
    stage = Zaber(config)
    stage.scan_range()