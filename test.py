import numpy as np
import pyvisa as pv

rm = pv.ResourceManager()
rm.list_resources()

'''
movable stage is ASRL3, X-LSM050A
'''

instr = rm.open_resource('ASRL3::INSTR')
instr.write('/1 move abs 10000')
print(instr.read())
