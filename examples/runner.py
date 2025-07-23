from fmpy import *
from fmpy.util import plot_result  # import the plot function
import numpy as np
# fmu = '../LinearTransform.fmu'
input_values = {}
fmu = 'dahlquist.fmu'
# input_values = {'n': 4, 'm': 4}
# input_values = {}
dump(fmu)  # get information

result = simulate_fmu(fmu, start_time=0, stop_time=1, step_size=1e-3, fmi_call_logger=lambda s: print('[FMI] ' + s), debug_logging=True)


plot_result(result)                # plot two variables
