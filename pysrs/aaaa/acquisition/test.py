import numpy as np

x = [1,1,1,2,2,2,3,3,3,4,4,4,5,5,5,6,6,6,7,7,7,8,8,8,9,9,9]
data = np.array(x)
print(x)
print(data)
print(x.reshape(3,3,3))
print(data.reshape(3,3,3))