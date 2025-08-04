# Co-simulation Examples

Co-simulation FMUs are self-contained simulation units that manage their own time stepping and internal solver. Unlike Model Exchange FMUs, Co-simulation FMUs encapsulate both the model equations and the numerical methods used to solve them. The master algorithm coordinates multiple FMUs by calling their `do_step()` method and exchanging input/output values.

## Key Concepts

### Co-simulation vs Model Exchange
- **Co-simulation**: FMU manages its own time stepping with `do_step()` method
- **Model Exchange**: External solver manages time stepping and calls derivative functions

### FMU Lifecycle
The typical Co-simulation FMU lifecycle follows this sequence:
1. **Instantiation**: Create FMU instance with `fmi3InstantiateCoSimulation()`
2. **Initialization**: Set parameters and inputs with `fmi3EnterInitializationMode()`
3. **Simulation**: Repeatedly call `fmi3DoStep()` to advance time
4. **Termination**: Clean up with `fmi3Terminate()` and `fmi3FreeInstance()`

### Required Methods
For Co-simulation FMUs, you must implement:
- `__init__()`: Initialize variables and register them
- `do_step()`: Advance simulation by one time step
- Optional: `enter_initialization_mode()`, `exit_initialization_mode()`, `terminate()`

## Key Implementation Details

### Variable Registration
Co-simulation FMUs support various variable types and causalities:

<!-- skip-test -->
```python
# Input variables (set by master algorithm)
self.register_variable(Float64("input_signal", causality=Fmi3Causality.input, start=0.0))

# Output variables (read by master algorithm)
self.register_variable(Float64("output_signal", causality=Fmi3Causality.output))

# Parameters (configurable, usually fixed during simulation)
self.register_variable(Float64("gain", causality=Fmi3Causality.parameter,
                              variability=Fmi3Variability.tunable, start=1.0))
```
<!-- /skip-test -->

### PID Controller Example
```python
from pythonfmu3 import Fmi3Causality, Fmi3Slave, Float64

class PIDController(Fmi3Slave):
    """PID Controller implementation"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "PythonFMU3 Team"
        self.description = "PID Controller"

        # Inputs
        self.setpoint = 0.0
        self.measurement = 0.0
        
        # Outputs
        self.control_output = 0.0

        # Parameters
        self.kp = 1.0  # Proportional gain
        self.ki = 0.1  # Integral gain
        self.kd = 0.01 # Derivative gain

        # Internal states
        self.integral_error = 0.0
        self.previous_error = 0.0
        self.first_step = True

        # Register variables
        self.register_variable(Float64("setpoint", causality=Fmi3Causality.input, start=0.0))
        self.register_variable(Float64("measurement", causality=Fmi3Causality.input, start=0.0))
        self.register_variable(Float64("output", causality=Fmi3Causality.output))
        self.register_variable(Float64("Kp", causality=Fmi3Causality.parameter, start=1.0))
        self.register_variable(Float64("Ki", causality=Fmi3Causality.parameter, start=0.1))
        self.register_variable(Float64("Kd", causality=Fmi3Causality.parameter, start=0.01))

    def do_step(self, current_time, step_size):
        # Calculate error
        error = self.setpoint - self.measurement

        # Proportional term
        p_term = self.kp * error

        # Integral term
        self.integral_error += error * step_size
        i_term = self.ki * self.integral_error

        # Derivative term
        if self.first_step:
            d_term = 0.0
            self.first_step = False
        else:
            d_term = self.kd * (error - self.previous_error) / step_size

        # PID output
        self.control_output = p_term + i_term + d_term

        # Store error for next iteration
        self.previous_error = error

        return True

```

### Units

Units can be added to this example through the `Unit` class along with `register_units` and the `unit` kwarg in `register_variable`

<!-- skip-test -->
```python
from pythonfmu3 import Unit
velocity_unit = Unit(name="m/s", m=1, s=-1)
```
which can now be utilized in the register variables call,
```
velocity_unit =  Unit(name="m/s", m=1, s=-1)
self.register_units([velocity_unit])
self.register_variable(Float64("v", causality=Fmi3Causality.output, start=0, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact, unit=velocity_unit.name))
```
<!-- /skip-test -->

### Arrays
If numpy is installed, arrays may be used with,

```python
from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Float64, UInt64, Fmi3Initial, Dimension
import numpy as np


class LinearTransform(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "..."
        self.description = "LinearTransform"

        self.time = 0.0
        self.m = 2
        self.n = 2

        self.scalar = 2.00

        self.u = np.array([1.0, 2.0]).reshape((self.m, 1))
        self.offset = np.array([1.0, 2.0]).reshape((self.m, 1))
        self.A = np.array([1.0, 1.0, 2.0, 1.0]).reshape((self.m, self.n))
        self.y = np.array([0.0, 0.0]).reshape((self.m, 1))


        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(UInt64("m", causality=Fmi3Causality.structuralParameter, variability=Fmi3Variability.tunable, start=2))
        self.register_variable(Float64("scalar", causality=Fmi3Causality.input, start=2.0))
        self.register_variable(Float64("u", causality=Fmi3Causality.input, dimensions=[Dimension(start=f"{self.n}")]))
        self.register_variable(Float64("offset", causality=Fmi3Causality.input, dimensions=[Dimension(start=f"{self.m}")]))
        self.register_variable(Float64("A", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable, dimensions=[Dimension(start=f"{self.m}"), Dimension(start=f"{self.n}")]))
        self.register_variable(Float64("y", causality=Fmi3Causality.output, dimensions=[Dimension(valueReference="1")]))

    def do_step(self, current_time, step_size):
        self.y = self.scalar*self.A.dot(self.u) + self.offset
        return True
```

The `do_step` function can also return a tuple of flags, corresponding to those expected by the FMI standard. This can be achieved through use of the `FmiStepResult` tuple,


```python
from pythonfmu3 import Fmi3Status, Fmi3StepResult

def do_step(self, current_time, step_size):
    self.y = 1 + 2 + 3 + 4 + ...
    terminate = False
    status = Fmi3Status.ok
    return Fmi3StepResult(status=Fmi3Status.ok, terminateSimulation=terminate)
```

### Create the FMU

```bash
    pythonfmu3 build -f pythonslave.py myproject
```

In this example a python class named `PythonSlave` that extends `Fmi3Slave` is declared in a file named `pythonslave.py`,
where `myproject` is an optional folder containing additional project files required by the python script.
Project folders such as this will be recursively copied into the FMU. Multiple project files/folders may be added.

## Integration and Testing

### Using FMPy for Testing
<!-- skip-test -->
```python
# Example of co-simulation setup
import fmpy
from fmpy import simulate_fmu
import matplotlib.pyplot as plt

# Simulate the PID controller FMU
result = simulate_fmu(
    filename='PIDController.fmu',
    start_time=0.0,
    stop_time=10.0,
    step_size=0.01,
    start_values={
        'Kp': 2.0,
        'Ki': 0.5,
        'Kd': 0.1,
        'setpoint': 1.0
    },
    input={
        'measurement': [(0.0, 0.0), (1.0, 0.3), (5.0, 0.8), (10.0, 1.0)]
    }
)

# Plot results
plt.figure(figsize=(12, 6))
plt.subplot(2, 1, 1)
plt.plot(result['time'], result['setpoint'], label='Setpoint')
plt.plot(result['time'], result['measurement'], label='Measurement')
plt.ylabel('Value')
plt.legend()
plt.grid(True)

plt.subplot(2, 1, 2)
plt.plot(result['time'], result['output'], label='Control Output')
plt.xlabel('Time [s]')
plt.ylabel('Control Signal')
plt.legend()
plt.grid(True)
plt.show()
```
<!-- /skip-test -->