import numpy as np
import pyvisa as pv

rm = pv.ResourceManager()
rm.list_resources()

'''
movable stage is ASRL3, X-LSM050A
'''