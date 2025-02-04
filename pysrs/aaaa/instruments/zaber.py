import numpy as np
from zaber_motion import Units
from zaber_motion.ascii import Connection
import concurrent.futures

class ZaberStage:
    def __init__(self, port: str) -> None:
        '''create an object for the zaber stage

        args: 
            port: str, COM port for the stage, e.g. 'COM3'
            
        returns: none
        '''

        self.port = port
        self.connection = None
        self.device = None
        self.axis = None

    def connect(self, timeout: int = 10) -> None:
        '''connect to the zaber stage in a threaded process
        
        args: 
            timeout: time to wait before giving up on connection

        returns: none
        '''

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor: # failed attempt to get it to not crash if it cant connect
            future = executor.submit(self._connect)
            future.result(timeout=timeout)

    def _connect(self):
        '''helper method for connection to the zaber stage

        args: none

        returns: none        
        '''

        if self.connection is not None:
            return  # do not attempt a reconnect if already connected
        
        self.connection = Connection.open_serial_port(self.port)
        self.connection.enable_alerts()
        devices = self.connection.detect_devices()
        if not devices:
            raise RuntimeError("No Zaber devices found.")
        
        self.device = devices[0]
        self.axis = self.device.get_axis(1)
        if not self.axis.is_homed():
            self.axis.home()

    def move_absolute_um(self, position_um: int):
        '''move the zaber stage in micrometers
        
        args: 
            position_um: location to move the stage to in micrometers, max 1e5

        returns: none
        '''

        if self.axis is None:
            self.connect()
        position_mm = position_um * 1e-3
        self.axis.move_absolute(position_mm, Units.LENGTH_MILLIMETRES)
        self.axis.wait_until_idle()

    def disconnect(self):
        '''cleanly reset and disconnect from the zaber stage
        
        args: none
        
        returns: none
        '''

        if self.connection:
            self.connection.close()
            self.connection = None

if __name__ == '__main__':
    config = {
        'serial': 'COM3', 
        'num_shifts': 3,  
        'shift_size': 5,  # mm
        'shift_offset': 20,  # mm
    }
    stage = ZaberStage(config)
    stage.scan_range()