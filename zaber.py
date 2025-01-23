import numpy as np
import pyvisa as pv
import serial
from zaber_motion import Units
from zaber_motion.ascii import Connection

'''
DONE: connection to zaber movable delay stage  X-LSM050A
'''


with Connection.open_serial_port("COM3") as connection:
    connection.enable_alerts()
    device_list = connection.detect_devices()
    print(f'Found {len(device_list)} devices')
    if len(device_list) > 0:
        device = device_list[0]
        print(f"Device detected: {device}")
        axis = device.get_axis(1)
        if not axis.is_homed():
            axis.home()
        axis.move_absolute(10, Units.LENGTH_MILLIMETRES)
        axis.move_relative(5, Units.LENGTH_MILLIMETRES)
    else:
        print("No devices detected.")
    