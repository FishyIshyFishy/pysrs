import nidaqmx
from nidaqmx.constants import AcquisitionType
import numpy as np
import matplotlib.pyplot as plt
import time
from pysrs.instruments.galvo_funcs import Galvo

@staticmethod
def lockin_scan(lockin_chan: str, galvo: Galvo) -> np.ndarray: # lockin_chan must be of the formal 'Dev1/ao0'
    with nidaqmx.Task() as ao_task, nidaqmx.Task() as ai_task:
        # configure galvos (ao) and lockin (ai)
        ao_task.ao_channels.add_ao_voltage_chan(f'{galvo.device}/{galvo.ao_chans[0]}')
        ao_task.ao_channels.add_ao_voltage_chan(f'{galvo.device}/{galvo.ao_chans[1]}')
        ai_task.ai_channels.add_ai_voltage_chan(lockin_chan)

        # configure timing
        ao_task.timing.cfg_samp_clk_timing(
            rate=galvo.rate,
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=galvo.total_samples # waveform.shape[1] = total samples
        )
        ai_task.timing.cfg_samp_clk_timing(
            rate=galvo.rate,
            source=f'/{galvo.device}/ao/SampleClock',
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=galvo.total_samples
        )

        # start tasks
        tic = time.time()
        # print('starting scan')
        ao_task.write(galvo.waveform, auto_start=False)
        ai_task.start() # start ai first to avoid losing initial samples
        ao_task.start()
        ao_task.wait_until_done(timeout=galvo.total_samples/galvo.rate + 5)
        ai_task.wait_until_done(timeout=galvo.total_samples/galvo.rate + 5)

        lockin_data = np.array(ai_task.read(number_of_samples_per_channel=galvo.total_samples))
        # print(f'scan complete in {time.time() - tic} seconds')

    lockin_data = lockin_data.reshape(galvo.numsteps_y, galvo.numsteps_x, galvo.pixel_samples)
    data = np.mean(lockin_data, axis=2)
    return data

def plot_image(data: np.ndarray, galvo: Galvo, savedat=True) -> None:
    if savedat:
        np.savez(r'C:\\Users\\Lab Admin\\Documents\\PythonStuff\\pysrs\\data\\trial1.npz', data=data, **galvo.__dict__)

    plt.imshow(data, 
               extent=[-galvo.amp_x, galvo.amp_x, -galvo.amp_y, galvo.amp_y], 
               origin='lower', 
               aspect='auto', 
               cmap='gray')
    plt.colorbar(label="lockin amplitude (V)")
    plt.title("raster scanned image with data plotted from lockin")
    plt.xlabel('galvo x voltage')
    plt.ylabel('galvo y voltage')
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    config = {
        "device": 'Dev1',
        "ao_chans": ['ao1', 'ao0'], # galvo connections
        "amp_x": 0.5,
        "amp_y": 0.5,
        "rate": 1e5, # hz
        "numsteps_x": 100, 
        "numsteps_y": 100, 
        "dwell": 1e-5, # s
        "numsteps_extra": 50
    }
    galvo = Galvo(config)

    data = lockin_scan('Dev1/ai0', galvo)
    plot_image(data, galvo)