import nidaqmx
import zaber_motion
import numpy as np
import matplotlib.pyplot as plt

class Galvo:
    def __init__(self, config, **kwargs):
        defaults = {
            "x_numsteps": 400,
            "y_numsteps": 400,
            "extra_steps": 100,
            "x_offset": -1.2,
            "y_offset": 1.5,
            "x_step": 0,
            "y_step": 0,
            "dwell": 10,
            # also need "control tuning point"
        }

        defaults.update(config)
        defaults.update(kwargs)
        for key, val in defaults.items():
            setattr(self, key, val)

    def get_step(self):
        return 0

    def get_offset():
        return 0

    def get_dwell():
        return 0
    
    def scan(self):
        return 0