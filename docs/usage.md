# Co-Simulation

A Co-Simulation FMU advances itself: the importer (the simulation tool that loads the
FMU) sets the inputs, asks the FMU to step forward with `do_step`, reads the outputs, and
exchanges them with the other models in the simulation. How the FMU gets from one
communication point to the next is up to you, which makes Co-Simulation the natural
choice for controllers, logic, and models with their own solver.

In Model Exchange, by contrast, the FMU only provides derivatives and the importer's
solver integrates them; see [Model Exchange](usageMX.md).

## Writing a model

Subclass `Fmi3Slave` and, in `__init__`, create your attributes and register the ones the
importer should see as variables. Then implement `do_step`:

- `do_step(current_time, step_size)` advances the model from `current_time` to
  `current_time + step_size`. Return `True` for success, `False` to discard the step (the
  importer may retry with a smaller step), or an `Fmi3StepResult` (see
  [Step results](#step-results)).
- Update `self.time` at the end of the step.

Create each attribute **before** registering it: `register_variable` only creates a
setter for attributes that already exist, and without a setter the importer can't set
inputs or parameters. If a value lives somewhere else, pass `getter=` and `setter=`
functions instead.

Set `self.author`, `self.description`, `self.license`, `self.version` and
`self.copyright` in `__init__`; they go into the model description. Keep one model class
per script.

### What the importer calls, and what runs in your class

| Importer calls | PythonFMU3 runs | Use it to |
| --- | --- | --- |
| `fmi3InstantiateCoSimulation` | `__init__(**kwargs)` | create attributes and register variables. `self.resources` is the FMU's resources folder, for data files |
| `fmi3Set...` / `fmi3Get...` | the variables' setters and getters (your attributes) | |
| `fmi3EnterInitializationMode` | `enter_initialization_mode()` | optional |
| `fmi3ExitInitializationMode` | `exit_initialization_mode()` | optional: compute values that depend on the parameters the importer set |
| `fmi3DoStep` | `do_step(current_time, step_size)` | advance the model |
| `fmi3Terminate` | `terminate()` | optional: close files, write results |

Parameters are set before `fmi3ExitInitializationMode`, so anything derived from them
(array sizes, precomputed constants, initial outputs) belongs in
`exit_initialization_mode`, not in `__init__`, which runs before the importer has set
anything.

## Variables explained

Every variable has a type (`Float64`, `Int32`, `Int64`, `UInt64`, `Boolean`, `String`,
`Enumeration`), a **causality** (who sets it) and a **variability** (when it can change).

| Causality | Meaning | Typical variability |
| --- | --- | --- |
| `input` | Set by the importer before each step, typically from another model's output | `continuous` (Float64) or `discrete` |
| `output` | Computed by your model, read by the importer | `continuous` (Float64) or `discrete` |
| `parameter` | A value the user sets before the simulation | `fixed` or `tunable` |
| `calculatedParameter` | Computed from parameters, constant during the simulation | `fixed` or `tunable` |
| `structuralParameter` | Changes the model's structure, such as array sizes; set in Configuration Mode | `fixed` or `tunable` |
| `local` | Internal, but visible to the importer for plotting and debugging | any |
| `independent` | Time. Exactly one, a `Float64` with variability `continuous` | `continuous` |

| Variability | Can change |
| --- | --- |
| `constant` | Never |
| `fixed` | Only before the simulation starts (until `exit_initialization_mode`) |
| `tunable` | Between steps, when the importer sets it; typically used for parameters |
| `discrete` | Only at steps or events. The default for Int32, Boolean, String and the other non-Float64 types |
| `continuous` | At any time. Only `Float64` variables can be continuous |

Give inputs and parameters a `start` value: it is the value importers show and use
until they set their own. `initial` (`exact`, `approx` or `calculated`) says how a start
value is used; the defaults suit most models, and you only need it for Model Exchange
states (`initial=Fmi3Initial.exact`).

<!-- skip-test -->
```python
# An input, set by the importer before each step
self.register_variable(Float64("u", causality=Fmi3Causality.input, start=0.0))

# An output, computed by the model
self.register_variable(Float64("y", causality=Fmi3Causality.output))

# A parameter the user can change between steps
self.register_variable(Float64("gain", causality=Fmi3Causality.parameter,
                               variability=Fmi3Variability.tunable, start=1.0))

# An integer mode switch: non-Float64 types are discrete (or fixed/tunable as parameters)
self.register_variable(Int32("mode", causality=Fmi3Causality.parameter,
                             variability=Fmi3Variability.fixed, start=0))
```
<!-- /skip-test -->

## Examples

### PID Controller Example
```python
from pythonfmu3 import Fmi3Causality, Fmi3Slave, Fmi3Variability, Float64

class PIDController(Fmi3Slave):
    """PID Controller implementation"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "PythonFMU3 Team"
        self.description = "PID Controller"

        self.time = 0.0

        # Inputs
        self.setpoint = 0.0
        self.measurement = 0.0

        # Outputs
        self.output = 0.0

        # Parameters
        self.Kp = 1.0   # Proportional gain
        self.Ki = 0.1   # Integral gain
        self.Kd = 0.01  # Derivative gain

        # Internal states
        self.integral_error = 0.0
        self.previous_error = 0.0
        self.first_step = True

        # Register variables
        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("setpoint", causality=Fmi3Causality.input, start=0.0))
        self.register_variable(Float64("measurement", causality=Fmi3Causality.input, start=0.0))
        self.register_variable(Float64("output", causality=Fmi3Causality.output))
        self.register_variable(Float64("Kp", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable, start=1.0))
        self.register_variable(Float64("Ki", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable, start=0.1))
        self.register_variable(Float64("Kd", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable, start=0.01))

    def do_step(self, current_time, step_size):
        # Calculate error
        error = self.setpoint - self.measurement

        # Proportional term
        p_term = self.Kp * error

        # Integral term
        self.integral_error += error * step_size
        i_term = self.Ki * self.integral_error

        # Derivative term
        if self.first_step:
            d_term = 0.0
            self.first_step = False
        else:
            d_term = self.Kd * (error - self.previous_error) / step_size

        # PID output
        self.output = p_term + i_term + d_term

        # Store error for next iteration
        self.previous_error = error

        self.time = current_time + step_size
        return True

```

### Units

Units are declared with the `Unit` class (SI base-unit exponents as keyword arguments),
registered with `register_units`, and referenced by name through the `unit` argument of a
variable:

<!-- skip-test -->
```python
from pythonfmu3 import Unit

# inside __init__
velocity_unit = Unit(name="m/s", m=1, s=-1)
self.register_units([velocity_unit])

self.v = 0.0
self.register_variable(Float64("v", causality=Fmi3Causality.output, start=0, variability=Fmi3Variability.continuous,
                               initial=Fmi3Initial.exact, unit=velocity_unit.name))
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

Arrays are NumPy arrays of the declared size. A dimension is either a fixed size
(`Dimension(start="2")`) or the value reference of a structural parameter
(`Dimension(valueReference="1")`, here `m`), which tells importers where the size comes
from.

PythonFMU3 doesn't resize your arrays when an importer changes a structural parameter in
Configuration Mode: make the parameter a Python property whose setter reallocates them.
The [1D pipe flow example](https://github.com/StephenSmith25/PythonFMU3/tree/HEAD/examples/pipe_cht)
does this for its number of segments `N`.

### Step results

Instead of `True`/`False`, `do_step` can return an `Fmi3StepResult` with the flags the FMI
standard defines for `fmi3DoStep`:

| Field | Default | Meaning |
| --- | --- | --- |
| `status` | `Fmi3Status.ok` | Status of the step (`ok`, `warning`, `discard`, `error`, `fatal`) |
| `terminateSimulation` | `False` | The model asks the importer to stop the simulation |
| `eventHandlingNeeded` | `False` | Passed to the importer as `eventHandlingNeeded` |
| `earlyReturn` | `False` | Passed to the importer as `earlyReturn` |

```python
from pythonfmu3 import Fmi3Status, Fmi3StepResult

def do_step(self, current_time, step_size):
    self.y = self.scalar * self.A.dot(self.u) + self.offset
    finished = current_time + step_size >= 10.0
    return Fmi3StepResult(status=Fmi3Status.ok, terminateSimulation=finished)
```

### Logging

`self.log(msg, status=Fmi3Status.ok, category=None, debug=False)` sends a message to the
importer's logger. If `category` is omitted it is derived from the status
(`logStatusWarning`, `logStatusError`, ...); debug messages are only forwarded when the
importer enables debug logging. Exceptions raised in your code are reported with their
Python traceback and make the call fail with `fmi3Fatal`.

## Building the FMU

```bash
pythonfmu3 build -f pid_controller.py                      # writes PIDController.fmu here
pythonfmu3 build -f pid_controller.py -d build             # ...into build/
pythonfmu3 build -f model.py lookup_table.csv data/        # with extra files and folders
```

The FMU is named after the class. Extra files and folders listed after the script are
copied into the FMU's `resources/` folder next to your script, so the model can open them
relative to its own file, or through `self.resources`. Pass a `requirements.txt` the same
way to ship your dependencies (see [Dependencies](dependencies.md)).

Build options set capability flags in the model description:

| Option | Effect |
| --- | --- |
| `--handle-state` | Importers may save and restore the FMU's state (`canGetAndSetFMUState`) |
| `--serialize-state` | ...and serialize it to bytes (`canSerializeFMUState`) |
| `--no-variable-step` | The FMU only handles a constant step size (`canHandleVariableCommunicationStepSize=false`) |
| `--only-one-per-process` | Importers may create only one instance per process |
| `--no-external-tool` | Sets `needsExecutionTool=false` |
| `--doc FOLDER` | Include a documentation folder |
| `--terminals FILE` | Include a `terminalsAndIcons.xml` |
| `-d DIR` | Where to write the FMU (default: the current folder) |

## Integration and Testing

### Using FMPy for Testing
<!-- skip-test -->
```python
# Simulate the FMU with FMPy
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