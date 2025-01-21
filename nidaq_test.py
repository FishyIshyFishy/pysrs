import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx.stream_readers import CounterReader
import numpy

system = nidaqmx.system.System.local()
DAQ_device = system.devices['DAQ1'] 
names = [ci.name for ci in DAQ_device.ci_physical_chans]
print(names)

other_names = [co.name for co in DAQ_device.co_physical_chans]
print(other_names)