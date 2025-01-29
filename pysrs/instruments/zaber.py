import numpy as np
from zaber_motion import Units
from zaber_motion.ascii import Connection

class ZaberStage:
    """Simple object to hold a Zaber and move it in micrometers."""
    def __init__(self, port='COM3'):
        self.port = port
        self.connection = None
        self.device = None
        self.axis = None

    def connect(self):
        """Connects to the Zaber stage and homes it if needed."""
        if self.connection is not None:
            return  # Already connected
        self.connection = Connection.open_serial_port(self.port)
        self.connection.enable_alerts()
        devices = self.connection.detect_devices()
        if not devices:
            raise RuntimeError("No Zaber devices found.")
        self.device = devices[0]
        self.axis = self.device.get_axis(1)
        if not self.axis.is_homed():
            print("Homing the stage...")
            self.axis.home()

    def move_absolute_um(self, position_um):
        """
        Move stage to an absolute position in micrometers.
        If your stage is in mm or has a different resolution, adapt accordingly.
        """
        if self.axis is None:
            self.connect()
        # Suppose your stage units are in millimeters:
        position_mm = position_um * 1e-3
        self.axis.move_absolute(position_mm, Units.LENGTH_MILLIMETRES)
        self.axis.wait_until_idle()

    def disconnect(self):
        """Close the connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

if __name__ == '__main__':
    config = {
        'serial': 'COM3', 
        'num_shifts': 200,  
        'shift_size': 10,  # um
        'shift_offset': 10,  # mm
    }
    stage = ZaberStage(config)
    stage.scan_range()