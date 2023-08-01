from fmpy import *
from fmpy.util import plot_result  # import the plot function
fmu = '../Counter.fmu'
dump(fmu)  # get information
result = simulate_fmu(fmu, start_time=0, stop_time=1.5, step_size=1e-3, fmi_call_logger=lambda s: print('[FMI] ' + s))



plot_result(result)                # plot two variables