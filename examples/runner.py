from fmpy import *
from fmpy.util import plot_result  # import the plot function
import numpy as np
# fmu = '../LinearTransform.fmu'
input_values = {'m': 3, 'n': 3, 'A': np.array([1, 2, 3, 9, 11, 14, 12, 4, 8]), 'scalar': 10.0} 
fmu = 'LinearTransformVariable.fmu'
# input_values = {'n': 4, 'm': 4}
# input_values = {}
dump(fmu)  # get information

result = simulate_fmu(fmu, start_time=0, stop_time=1e-4, step_size=1e-3, fmi_call_logger=lambda s: print('[FMI] ' + s), start_values=input_values, debug_logging=True)


plot_result(result)                # plot two variables
