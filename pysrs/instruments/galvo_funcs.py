import nidaqmx
from nidaqmx.constants import AcquisitionType
import numpy as np
import matplotlib.pyplot as plt
import time


class Galvo:
    def __init__(self, config=None, **kwargs):
        defaults = {
            "x_numsteps": 400,  
            "y_numsteps": 400,  
            "extra_steps": 100,  # optional, for stability
            "x_offset": -1.2,  
            "y_offset": 1.5, 
            "x_step": 0,  
            "y_step": 0,  
            "dwell": 10,  # per (x,y) combo, in us
            "amp_x": 0.5, 
            "amp_y": 0.5,  
            "freq_x": 100,  # ignored for raster
            "freq_y": 1,  # ignored for raster
            "duration": 5,  
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
        num_xsteps = self.x_numsteps
        num_ysteps = self.y_numsteps

        x_rate = int(self.dwell * self.rate)
        num_samples = num_xsteps * x_rate  

        t_x = np.linspace(0, 1, x_rate, endpoint=False)
        x_waveform = np.concatenate([
            self.amp_x * (2 * (t_x % 1) - 1)  
            for _ in range(num_xsteps)
        ])

        y_steps = np.linspace(-self.amp_y, self.amp_y, num_ysteps)
        y_waveform = np.repeat(
            y_steps,
            num_xsteps * x_rate // num_ysteps
        )

        total_samples = len(x_waveform)
        if len(y_waveform) < total_samples:
            y_waveform = np.pad(y_waveform, (0, total_samples - len(y_waveform)), constant_values=y_waveform[-1])
        else:
            y_waveform = y_waveform[:total_samples]

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
        "duration": 5,
        "rate": 100,
        "x_numsteps": 100,  
        "y_numsteps": 100    # must be a integer divisor of x_numsteps for a true raster
    }

    galvo = Galvo(config)
    galvo.waveform = galvo.gen_raster()

    plt.figure(figsize=(10, 6))
    plt.plot(galvo.waveform[0], label='x, fast', color='black')
    plt.plot(galvo.waveform[1], label='y, slow', color='blue')
    plt.legend()
    plt.xlabel('Time, s')
    plt.ylabel('Voltage, V')
    plt.title('raster scan waveforms')
    plt.grid()
    plt.show()

    galvo.do_raster()
