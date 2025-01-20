import serial
import usb.core
import usb.util
from ctypes import CDLL, c_double
import nidaqmx
from nidaqmx.constants import VoltageUnits

''' 
a bunch of skeleton code that could be used for the galvos, but not actually connected to anything yet 
'''

ser = serial.Serial(port='COM5', baudrate=9600, timeout=1)
command = "MOVE 100 200\n"
ser.write(command.encode())

reply = ser.readline().decode()
print(f'reply: {reply}')

ser.close()

# usb core stuff
dev = usb.core.find(idVendor=0x1234, idProduct=0x5678)
if dev is None:
    raise ValueError('Device not found')

dev.write(1, b'hello', 1000)
reply = dev.read(0x81, 64)
print(f'usb core reply: {reply}')

# ctypes stuff
galvo_dll = CDLL('pathtodllfile.dll')
galvo_dll.MoveToPosition.argtypes = [c_double, c_double]
galvo_dll.MoveToPosition(100.0, 200.0)

with nidaqmx.Task() as task:
    task.ao_changes.add_ao_voltage_chan(
        "Dev1/a0", "X-axis", min_val=-10, max_val=10, units=VoltageUnits.VOLTS
    )
    task.ao_changes.add_ao_voltage_chan(
        "Dev1/a0", "Y-axis", min_val=-10, max_val=10, units=VoltageUnits.VOLTS
    )
    task.write([2.0, 3.0], auto_start=True) # arbitrary values until i figure out how to actually connect via bnc2110
    print('position command sent to galvo')

'''
todo list
- figure out how to see the different things connected to bnc 2110
- get galvo scanning units
- get lock in data
'''