from fmpy import *
from fmpy.fmi3 import FMU3Slave
import numpy as np

tmax = 1e-2
step_size = 1e-3
t = 0

fmu_name1= 'LinearTransformVariable.fmu'
model_description1 = read_model_description(fmu_name1)
unzipdir1 = extract(fmu_name1)

fmu = FMU3Slave(guid=model_description1.guid,
                    unzipDirectory=unzipdir1,
                    modelIdentifier=model_description1.coSimulation.modelIdentifier,
                    instanceName="Instance 1")


# array value references
m_vr = 1
n_vr = 2
A_vr = 6

# values
m = 10
n = 10
A = [1] * m * n

fmu.instantiate(loggingOn=True, eventModeUsed=False)

# setting arrays
fmu.fmi3EnterConfigurationMode(fmu.component)
fmu.setUInt64(vr=[m_vr, n_vr], values=[m, n])
fmu.fmi3ExitConfigurationMode(fmu.component)


fmu.enterInitializationMode()
fmu.setFloat64(vr=[A_vr], values=A)
fmu.exitInitializationMode()

while t < tmax:
    fmu.doStep(currentCommunicationPoint=t, communicationStepSize=step_size)
    t += step_size
    

print(fmu.getFloat64(vr=[7], nValues=m))
    

