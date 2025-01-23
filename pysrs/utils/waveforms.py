import numpy as np
import matplotlib.pyplot as plt

class Waveform:
    def __init__(self, amp, freq, duration, rate, type='sawtooth'):
        self.amp = amp
        self.freq = freq
        self.duration = duration
        self.rate = rate
        self.time = np.linspace(0, duration, int(rate * duration), endpoint=False)
        self.type = type

        match self.type:
            case 'sine': self.wave = self.sine()
            case 'tri': self.wave = self.tri()
            case 'sqaure': self.wave = self.square()
            case 'sawtooth': self.wave = self.sawtooth()
            case 'const': self.wave = self.const()
            case _:
                print('invalid waveform specified, using sawtooth')
                self.wave = self.sawtooth()

    def sine(self):
        self.waveform = self.amp * np.sin(2 * np.pi * self.freq * self.time)
        return self.waveform

    def tri(self):
        self.waveform = self.amp * (2 * np.abs(2 * (self.time * self.freq % 1) - 1) - 1)
        return self.waveform

    def square(self):
        self.waveform = self.amp * np.sign(np.sin(2 * np.pi * self.freq * self.time))
        return self.waveform

    def sawtooth(self):
        self.waveform = self.amp * (2 * (self.time * self.freq % 1) - 1)
        return self.waveform

    def const(self, value):
        self.waveform = np.full_like(self.time, value)
        return self.waveform