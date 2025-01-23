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
            "extra_steps": 100,  # optional, for stability
            "offset_x": -1.2,  
            "offset_y": 1.5, 
            "dwell": 10,  # per (x,y) combo, in us
            "amp_x": 0.5, 
            "amp_y": 0.5,  
            "rate": 10000,  # sampling rate
            "device": 'Dev1',  # nidaq device name
            "ao_chans": ['ao1', 'ao0']  # for galvos
        }

        try:
            if config:
                defaults.update(config)
        except Exception as e:
            print(f"Error - must pass a config to Galvo class: {e}")

        defaults.update(kwargs)
        for key, val in defaults.items():
            setattr(self, key, val)



    def gen_raster(self):
        self.dwell *= 1e-6  
        pixel_samples = max(1, int(self.dwell * self.rate))  
        total_rowsamples = pixel_samples * self.numsteps_x
        total_samples = total_rowsamples * self.numsteps_y

        x_row = np.linspace(-self.amp_x, self.amp_x, self.numsteps_x, endpoint=False)
        x_waveform = np.tile(np.repeat(x_row, pixel_samples), self.numsteps_y)

        y_steps = np.linspace(self.amp_y, -self.amp_y, self.numsteps_y)  
        y_waveform = np.repeat(y_steps, total_rowsamples)

        if len(x_waveform) < total_samples:
            x_waveform = np.pad(x_waveform, (0, total_samples - len(x_waveform)), constant_values=x_waveform[-1])
        else:
            x_waveform = x_waveform[:total_samples]

        return np.vstack([x_waveform, y_waveform])


    def do_raster(self):
        if not hasattr(self, 'waveform'): 
            self.waweform = self.gen_raster()
        print(f'waveform generated')

        with nidaqmx.Task() as task:
            for chan in self.ao_chans:
                task.ao_channels.add_ao_voltage_chan(f"{self.device}/{chan}")

            task.timing.cfg_samp_clk_timing(
                rate=self.rate,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=self.waveform.shape[1]
            )

            print(f'raster scanning with channels {self.ao_chans}')
            task.write(self.waveform, auto_start=True)
            task.wait_until_done()
            print('raster complete\n')



if __name__ == '__main__':
    config = {
        "device": 'Dev1',
        "ao_chans": ['ao1', 'ao0'],
        "amp_x": 0.5,
        "amp_y": 0.5,
        "rate": 1e5, # hz
        "numsteps_x": 100,  
        "numsteps_y": 100 , # must be a integer divisor of numsteps_x for a true raster
        "dwell": 10, # us
    }

    galvo = Galvo(config)
    galvo.waveform = galvo.gen_raster()

    times = np.arange(galvo.waveform.shape[1]) / config['rate'] 

    plt.figure(figsize=(10, 6))
    plt.plot(times, galvo.waveform[0], label='x, fast', color='black')
    plt.plot(times, galvo.waveform[1], label='y, slow', color='blue')
    plt.legend()
    plt.xlabel('Time (s)')
    plt.ylabel('Voltage (V)')
    plt.title('Raster Scan Waveforms with Time Axis')
    plt.grid()
    plt.tight_layout()
    plt.show()

   #  galvo.do_raster()
