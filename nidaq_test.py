import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx.stream_readers import CounterReader
import numpy

def setup(anout=False, anin=False, dig=False, cin=False, cout=False):
    system = nidaqmx.system.System.local()

    devices = [device.name for device in system.devices]
    print(f'available devices: {devices}\n\n')
    for device in system.devices:
        print(f'device: {device.name}')

        if anin: 
            print(f'analog inputs:')
            for ai_channel in device.ai_physical_chans: 
                print(f'    {ai_channel.name}')

        if anout: 
            print(f'analog outputs:')
            for ao_channel in device.ao_physical_chans: 
                print(f'    {ao_channel.name}')

        if dig: 
            print('digital lines:')
            for di_channel in device.di_lines: 
                print(f'    {di_channel.name}')
            for do_channel in device.do_lines: 
                print(f'    {do_channel.name}')

        if cin: 
            print('counter inputs:')
            for ci_channel in device.ci_physical_chans: 
                print(f'    {ci_channel.name}')

        if cout: 
            print('counter outputs:')
            for co_channel in device.co_physical_chans: 
                print(f'    {co_channel.name}')
        print('\n\n')

    
    return None

def test(device_name):
    with nidaqmx.Task() as task:
        for ai_channel in nidaqmx.system.System.local().devices[device_name].ai_physical_chans:
            print(f"AI Channel: {ai_channel.name}")
            
            task.ai_channels.add_ai_voltage_chan(ai_channel.name)

        task.start()
        data = task.read(number_of_samples_per_channel=1)
        print("Signal Data from Channels:")
        for i, ai_channel in enumerate(task.ai_channels):
            print(f"  {ai_channel.physical_channel.name}: {data[i]}")


if __name__ == '__main__':
    setup(anin=True, anout=True)