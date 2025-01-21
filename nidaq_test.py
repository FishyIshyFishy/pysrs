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


    # ['Dev1', 'SimDev1']

    # DAQ_device = system.devices['SimDev1'] 
    # ci_names = [ci.name for ci in DAQ_device.ci_physical_chans]
    # print(f'counter input names: {ci_names}')
    # # ['Dev1/ctr0', 'Dev1/ctr1', 'Dev1/ctr2', 'Dev1/ctr3']

    # co_names = [co.name for co in DAQ_device.co_physical_chans]
    # print(f'counter output names: {co_names}')
    # # ['Dev1/ctr0', 'Dev1/ctr1', 'Dev1/ctr2', 'Dev1/ctr3', 'Dev1/freqout']

# with nidaqmx.Task() as task:
#     task.ci_channels.add_ci_count_edges_chan(
#         "Dev1/ctr0", edge=Edge.RISING, initial_count=0
#     )
#     task.timing.cfg_implicit_timing(
#         sample_mode=AcquisitionType.CONTINUOUS, samps_per_chan=1000
#     )

#     task.start()

#     reader = CounterReader(task.in_stream)
#     data = reader.read_many_sample_uint32(
#         number_of_samples_per_channel=READ_ALL_AVAILABLE
#     )

#     print('Acquired %s samples' % len(data))
#     print(data)

if __name__ == '__main__':
    setup(anin=True, anout=True)