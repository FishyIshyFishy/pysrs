import nidaqmx
from nidaqmx.constants import AcquisitionType
import numpy as np
import matplotlib.pyplot as plt
import time
from PIL import Image


class Galvo:
    def __init__(self, config=None, rpoc_mask=None, ttl_channel=None, **kwargs):
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
        channels = list(self.ao_chans)  
        waveform = self.waveform.copy()
        if self.rpoc_mask is not None and self.ttl_channel is not None:
            ttl_wave = generate_ttl_waveform(self.rpoc_mask, self.pixel_samples, self.total_x, self.total_y, high_voltage=5.0)
            if ttl_wave.size != waveform.shape[1]:
                raise ValueError("TTL waveform length does not match scan waveform length!")
            waveform = np.vstack([waveform, ttl_wave])
            channels.append(self.ttl_channel)
            print('Raster complete')


@staticmethod
def generate_ttl_waveform(mask_image, pixel_samples, total_x, total_y, high_voltage=5.0):
    mask_arr = np.array(mask_image)
    binary_mask = (mask_arr > 128).astype(np.uint8)
    
    if binary_mask.shape != (total_y, total_x):
        mask_pil = Image.fromarray(binary_mask * 255)
        mask_resized = mask_pil.resize((total_x, total_y), Image.NEAREST)
        binary_mask = (np.array(mask_resized) > 128).astype(np.uint8)
    
    ttl_rows = [np.repeat(binary_mask[row, :], pixel_samples) for row in range(total_y)]
    ttl_wave = np.concatenate(ttl_rows)
    ttl_wave = ttl_wave * high_voltage
    return ttl_wave




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

    times = np.arange(galvo.waveform.shape[1]) / config['rate'] 

    plt.figure(figsize=(10, 6))
    plt.plot(times, galvo.waveform[0], label='x, fast', color='black')
    plt.plot(times, galvo.waveform[1], label='y, slow', color='blue')
    plt.legend()
    plt.xlabel('time, s')
    plt.ylabel('voltage, V') 
    plt.title('raster scan waveforms')
    plt.grid()
    plt.tight_layout()
    plt.show()

    # tic = time.time()
    # for _ in range(10):
    #     toc = time.time()
    #     galvo.gen_raster()
    #     print(f'individual scan: {time.time() - toc:.4f}\n')
    # print(f'total scanning time: {time.time() - tic:.2f} s')

