import nidaqmx
from nidaqmx.constants import AcquisitionType
import numpy as np
import matplotlib.pyplot as plt
import time


class Galvo:
    def __init__(self, config=None, **kwargs):
        # Default configuration
        defaults = {
            "x_numsteps": 400,  # Number of steps for X-axis
            "y_numsteps": 400,  # Number of steps for Y-axis
            "extra_steps": 100,  # Optional extra steps for stability
            "x_offset": -1.2,  # Offset for X-axis
            "y_offset": 1.5,  # Offset for Y-axis
            "x_step": 0,  # Step size for X-axis
            "y_step": 0,  # Step size for Y-axis
            "dwell": 10,  # Dwell time per point
            "amp_x": 0.5,  # X-axis amplitude
            "amp_y": 0.5,  # Y-axis amplitude
            "freq_x": 100,  # X-axis frequency (ignored for raster)
            "freq_y": 1,  # Y-axis frequency (ignored for raster)
            "duration": 5,  # Scan duration
            "rate": 10000,  # Sampling rate
            "device": 'Dev1',  # NI DAQ device name
            "ao_chans": ['ao1', 'ao0']  # Analog output channels
        }

        # Update defaults with user-specified config and kwargs
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
        waveform = self.gen_raster()

        with nidaqmx.Task() as task:
            for chan in self.ao_chans:
                task.ao_channels.add_ao_voltage_chan(f"{self.device}/{chan}")

            task.timing.cfg_samp_clk_timing(
                rate=self.rate,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=waveform.shape[1]
            )

            print(f'raster scanning with channels {self.ao_chans}')
            task.write(waveform, auto_start=True)
            task.wait_until_done()
            print('raster complete')


if __name__ == '__main__':
    # Configuration for the Galvo
    config = {
        "device": 'Dev1',
        "ao_chans": ['ao1', 'ao0'],
        "amp_x": 0.5,
        "amp_y": 0.5,
        "duration": 5,
        "rate": 100,
        "x_numsteps": 100,  # X-axis resolution (number of sweeps)
        "y_numsteps": 100    # Y-axis resolution (number of steps)
    }

    # Create Galvo object
    galvo = Galvo(config)

    # Generate the raster waveform
    waveform = galvo.gen_raster()

    # Visualize the waveform
    plt.figure(figsize=(10, 6))
    plt.plot(waveform[0], label='x, fast')
    plt.plot(waveform[1], label='y, slow')
    plt.legend()
    plt.xlabel('Time (s)')
    plt.ylabel('Voltage (V)')
    plt.title('Raster Scan Waveforms')
    plt.grid()
    plt.show()

    # Uncomment to perform the raster scan
    # galvo.do_raster()
