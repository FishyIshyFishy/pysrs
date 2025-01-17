import numpy as np
import pyvisa as pv
from zaber_motion import Units
from zaber_motion.ascii import Connection

def check_connection(port):
    try:
        rm = pv.ResourceManager()
        instr = rm.open_resource(f'ASRL{port}::INSTR')
        instr.write("/\n") 
        reply = instr.read('\n')
        # print(f"Response: {reply}")
        return None
    except Exception as e:
        print(f"Could not connect to device: {e}")
        return None
    

with Connection.open_serial_port("COM3") as connection:
    connection.enable_alerts()

    device_list = connection.detect_devices() # why wont it conencoiwanefgoweuibgwjbev,knabwe gawu4ebjil.,k
    # zaber console is moving the stage correctly, unsure why connecting through com3 here is not working

    print('Found {} devices'.format(len(device_list)))
    if len(device_list) > 0:
        device = device_list[0]  # 
        print(f"Device detected: {device}")
        axis = device.get_axis(1)
        if not axis.is_homed():
            axis.home()
        axis.move_absolute(10, Units.LENGTH_MILLIMETRES)
        axis.move_relative(5, Units.LENGTH_MILLIMETRES)
    else:
        print("No devices detected.")


'''
movable stage is ASRL3, X-LSM050A
'''

