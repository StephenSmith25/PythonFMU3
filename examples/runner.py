from fmpy import *
from fmpy.util import plot_result  # import the plot function
import numpy as np
fmu = '../LinearTransform.fmu'
input_values = {'A': np.array([1, 2, 3, 9]), 'offset': [9, 8], 'scalar': 10.0} 
#fmu = '../BouncingBall.fmu'
#input_values = {}
dump(fmu)  # get information

result = simulate_fmu(fmu, start_time=0, stop_time=1.5, step_size=1e-3, fmi_call_logger=lambda s: print('[FMI] ' + s), start_values=input_values)


plot_result(result)                # plot two variables