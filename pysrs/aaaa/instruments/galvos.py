import nidaqmx
from nidaqmx.constants import AcquisitionType
import numpy as np
import time
import matplotlib.pyplot as plt
from PIL import Image

class Galvo: 
    def __init__(self, config: dict = {}, amp_x: float = 0.5, amp_y: float = 0.5, numsteps_x: int = 100, numsteps_y: int = 100,
                extrasteps_left: int = 100, extrasteps_right: int = 100, offset_x: float = -1.2, offset_y: float = 1.5,
                dwell: float = 1e-5, rate: float = 1e6, device: str = 'Dev1', ao_chans: list = ['ao1, ao0']) -> None:
        '''create a Galvo object

        args: 
            config: hold all the parameters for the galvo for convenience
            amp_x, amp_y: amplitudes in V
            numsteps_x, numsteps_y: number of divisions within the amplitude in both directions
            extrasteps_left, extrasteps_right: number of padding steps in the -x and +x directions not plotted
            offset_x, offset_y: center voltage of the galvos
            dwell: real time to spend on any given (x,y) combination
            rate: sample rate for any galvo signals
            device: name of NI-DAQ device
            ao_chans: 2 analog output channels for the galvos

        returns: none
        '''
        
        self.amp_x = amp_x
        self.amp_y = amp_y
        self.numsteps_x = numsteps_x
        self.numsteps_y = numsteps_y
        self.extrasteps_left = extrasteps_left
        self.extrasteps_right = extrasteps_right
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.dwell = dwell
        self.rate = rate
        self.device = device
        self.ao_chans = ao_chans

        self.__dict__.update(config) # config gets the final say on what parameters are what
        
               
        self.pixel_samples = max(1, int(self.dwell * self.rate))
        self.total_x = self.numsteps_x + self.extrasteps_left + self.extrasteps_right
        self.total_y = self.numsteps_y # no padding in the slow y direction needed
        self.total_samples = self.total_x * self.total_y * self.pixel_samples
        
        self.waveform = self.gen_raster()


    def gen_raster(self) -> np.ndarray:
        '''generate a typical raster scan with x as the fast direction

        args: none

        returns: 2D array with arr[0] as the x waveform and arr[1] as the y waveform
        '''

        x_row = np.linspace(-self.amp_x, self.amp_x, self.total_x) + self.offset_x # [1,2,3]
        x_waveform = np.tile(np.repeat(x_row, self.pixel_samples), self.total_y) # [1,2,3,1,2,3,1,2,3]
        y_steps = np.linspace(self.amp_y, -self.amp_y, self.total_y) + self.offset_y # [4,5,6]
        y_waveform = np.repeat(y_steps, self.pixel_samples * self.total_x) # [4,4,4,5,5,5,6,6,6]

        composite = np.vstack([x_waveform, y_waveform])

        return composite
    

    @staticmethod
    def gen_wave(waveform: str, amplitude: float, frequency: float, duration: float, rate: float):
        '''generate a single channel waveform
        
        args:
            waveform: waveform variety to generate, supports "sine", "triangle", "square"
            amplitude: voltage amplitude in V
            frequency: real non-angular frequency in Hz
            duration: real time to send the waveform
            rate: sample rate for the signal
        
        returns: waveform of interest
        '''

        t = np.linspace(0, duration, int(rate * duration), endpoint=False)
        if waveform == "sine":
            return t, amplitude * np.sin(2 * np.pi * frequency * t)
        elif waveform == "triangle":
            return t, amplitude * (2 * np.abs(2 * (t * frequency % 1) - 1) - 1)
        elif waveform == "square":
            return t, amplitude * np.sign(np.sin(2 * np.pi * frequency * t))
        else:
            raise ValueError("not a valid waveform, use string input of 'sine', 'triangle', or 'square'.")
        

if __name__ == '__main__':
    config = {
        "device": 'Dev1',
        "ao_chans": ['ao1', 'ao0'],
        "amp_x": 0.5,
        "amp_y": 0.5,
        "rate": 1e5,  # Hz
        "numsteps_x": 100,
        "numsteps_y": 100,
        "dwell": 50e-6,
    }

    galvo = Galvo(config)
    galvo.waveform = galvo.gen_raster()
    print(galvo.waveform.shape)
    print(galvo.total_samples)

    # times = np.arange(galvo.waveform.shape[1]) / config['rate']
    # plt.figure(figsize=(10, 6))
    # plt.plot(times, galvo.waveform[0], label='x (fast axis)', color='black')
    # plt.plot(times, galvo.waveform[1], label='y (slow axis)', color='blue')
    # plt.xlabel('Time (s)')
    # plt.ylabel('Voltage (V)')
    # plt.title('Raster Scan Waveforms') 
    # plt.legend()
    # plt.grid()
    # plt.tight_layout()
    # plt.show()
