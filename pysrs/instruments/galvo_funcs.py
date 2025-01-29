import nidaqmx
from nidaqmx.constants import AcquisitionType
import numpy as np
import matplotlib.pyplot as plt
import time


class Galvo:
    def __init__(self, config=None, **kwargs):
        defaults = {
            "numsteps_x": 400,  
            "numsteps_y": 400,  
            "numsteps_extra": 100,  # Extra padding for stability
            "offset_x": -1.2,  
            "offset_y": 1.5, 
            "dwell": 10e-6,  # in microseconds
            "amp_x": 0.5, 
            "amp_y": 0.5,  
            "rate": 10000,  # Sampling rate
            "device": 'Dev1',  # NI-DAQ device name
            "ao_chans": ['ao1', 'ao0']  # Analog output channels for galvos
        }

        if config:
            defaults.update(config)
        defaults.update(kwargs)
        
        for key, val in defaults.items():
            setattr(self, key, val)

        self.pixel_samples = max(1, int(self.dwell * self.rate))
        
        self.total_x = self.numsteps_x + 2 * self.numsteps_extra
        self.total_y = self.numsteps_y + 2 * self.numsteps_extra
        self.total_samples = self.total_x * self.total_y * self.pixel_samples

        self.waveform = self.gen_raster()

    def gen_raster(self):
        total_rowsamples = self.pixel_samples * self.total_x

        x_row = np.linspace(-self.amp_x, self.amp_x, self.total_x, endpoint=False)
        x_waveform = np.tile(np.repeat(x_row, self.pixel_samples), self.total_y)

        y_steps = np.linspace(self.amp_y, -self.amp_y, self.total_y)
        y_waveform = np.repeat(y_steps, total_rowsamples)

        if len(x_waveform) < self.total_samples:
            x_waveform = np.pad(x_waveform, (0, self.total_samples - len(x_waveform)), constant_values=x_waveform[-1])
        else:
            x_waveform = x_waveform[:self.total_samples]

        return np.vstack([x_waveform, y_waveform])

    def do_raster(self):
        if not hasattr(self, 'waveform'): 
            self.waveform = self.gen_raster()
        print(f'Waveform generated')

        with nidaqmx.Task() as task:
            for chan in self.ao_chans:
                task.ao_channels.add_ao_voltage_chan(f"{self.device}/{chan}")

            task.timing.cfg_samp_clk_timing(
                rate=self.rate,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=self.waveform.shape[1]
            )

            print(f'Raster scanning with channels {self.ao_chans}')
            task.write(self.waveform, auto_start=True)
            task.wait_until_done()
            print('Raster complete')



if __name__ == '__main__':
    config = {
        "device": 'Dev1',
        "ao_chans": ['ao1', 'ao0'],
        "amp_x": 0.5,
        "amp_y": 0.5,
        "rate": 1e5, # hz
        "numsteps_x": 100,  
        "numsteps_y": 100 , # must be a integer divisor of numsteps_x for a true raster
        "dwell": 50e-6, # us
    }

    galvo = Galvo(config)
    galvo.waveform = galvo.gen_raster()

    # times = np.arange(galvo.waveform.shape[1]) / config['rate'] 

    # plt.figure(figsize=(10, 6))
    # plt.plot(times, galvo.waveform[0], label='x, fast', color='black')
    # plt.plot(times, galvo.waveform[1], label='y, slow', color='blue')
    # plt.legend()
    # plt.xlabel('time, s')
    # plt.ylabel('voltage, V') 
    # plt.title('raster scan waveforms')
    # plt.grid()
    # plt.tight_layout()
    # plt.show()

    tic = time.time()
    for _ in range(10):
        toc = time.time()
        galvo.do_raster()
        print(f'individual scan: {time.time() - toc:.4f}\n')
    print(f'total scanning time: {time.time() - tic:.2f} s')
