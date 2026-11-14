# Migrating from PythonFMU

[PythonFMU](https://github.com/NTNU-IHB/PythonFMU) exports FMI 2.0 Co-simulation FMUs.
PythonFMU3 started as a fork of it and exports FMI 3.0 Co-simulation and Model Exchange
FMUs. A model is written the same way in both: a class that registers its attributes as
variables and implements `do_step`. Most of the translation is renaming. This page lists
the renames and the few behaviour changes to check.

PythonFMU3 builds **FMI 3.0** FMUs only, so the simulator using them must support FMI 3.0
(for example FMPy, OMSimulator or `fmusim`). If you still need FMI 2.0 FMUs, keep
PythonFMU for those; both packages can be installed side by side.

## Quick reference

| PythonFMU (FMI 2.0) | PythonFMU3 (FMI 3.0) |
| --- | --- |
| `pip install pythonfmu` | `pip install pythonfmu3` |
| `from pythonfmu import ...` | `from pythonfmu3 import ...` |
| `Fmi2Slave` | `Fmi3Slave` (Co-simulation); `Fmi3SlaveBase` + `ModelExchange` for Model Exchange |
| `Fmi2Causality`, `Fmi2Variability`, `Fmi2Initial`, `Fmi2Status` | `Fmi3Causality`, `Fmi3Variability`, `Fmi3Initial`, `Fmi3Status` (same members) |
| `Real` | `Float64` |
| `Integer` | `Int32` (FMI 2.0 integers are 32-bit); `Int64` and `UInt64` also exist |
| `Boolean`, `String` | unchanged |
| time is implicit | register a `Float64` with `causality=Fmi3Causality.independent` |
| `setup_experiment(start_time, stop_time, tolerance)` | not called: use `enter_initialization_mode()` |
| `do_step(...)` returns `bool` | returns `bool` or an `Fmi3StepResult` |
| class attributes `author = ...`, `description = ...` | set them in `__init__` (`self.author = ...`) |
| `pythonfmu build -f model.py` | `pythonfmu3 build -f model.py` |
| `pythonfmu deploy -f model.fmu` | `pythonfmu3 deploy -f model.fmu` |
| `pythonfmu buildcsv` | not available |
| `--interpolate-inputs` | not available |

These are unchanged: `register_variable` (including `getter=`/`setter=` and dotted names
for nested objects), `enter_initialization_mode`, `exit_initialization_mode`,
`terminate`, `self.log(...)`, `self.resources`, `DefaultExperiment`, project files and
the `requirements.txt`/`environment.yml` deployment, and the `--no-external-tool`,
`--no-variable-step`, `--only-one-per-process`, `--handle-state` and
`--serialize-state` build options.

New in PythonFMU3: Model Exchange, `Int64`/`UInt64`/`Enumeration` variables, NumPy array
variables, units, structural parameters and `Fmi3StepResult`. See the
[Co-simulation](usage.md) and [Model Exchange](usageMX.md) pages.

## Step by step

### 1. Rename imports, classes and types

Replace `pythonfmu` with `pythonfmu3`, every `Fmi2...` with `Fmi3...`, `Real` with
`Float64` and `Integer` with `Int32`.

Integer, Boolean and String variables can't be continuous. FMI treats a missing
variability as continuous, so give them `variability=Fmi3Variability.discrete` (or
`fixed`, `tunable` or `constant` for parameters). PythonFMU didn't check this either, so
migration is a good moment to fix it.

### 2. Declare time

FMI 2.0 FMUs had an implicit time variable. In FMI 3.0 the independent variable is
declared like any other, so register one and keep it up to date:

```python skip
self.time = 0.0
self.register_variable(Float64("time", causality=Fmi3Causality.independent,
                               variability=Fmi3Variability.continuous))
```

In `do_step`, set `self.time = current_time + step_size`. Model Exchange classes must
define `self.time` (the importer sets it).

### 3. Move class-level metadata into `__init__`

PythonFMU read `author`, `description`, `license`, `version` and `copyright` from class
attributes. PythonFMU3 only uses instance attributes, so class-level values are silently
dropped from the model description. Set them after `super().__init__(**kwargs)`:

```python skip
def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.author = "Jane Doe"
    self.description = "Integrates its input"
```

### 4. Replace `setup_experiment`

FMI 3.0 removed `fmi2SetupExperiment`; the start time, stop time and tolerance are
passed to `fmi3EnterInitializationMode` instead. PythonFMU3 never calls
`setup_experiment`, and does not pass these values to Python. Move any initialisation you
did there into `enter_initialization_mode()` (or `exit_initialization_mode()`), and use
`current_time` in `do_step` if you need the time.

### 5. Check variable names that start with `_`

PythonFMU3 strips leading underscores when it looks up the attribute behind a variable:
`Float64("_x")` reads and writes `self.x`, not `self._x`. Either rename such variables or
pass `getter=` and `setter=` explicitly.

### 6. Rebuild and test

```bash
pip install pythonfmu3
pythonfmu3 build -f model.py
```

Then run the new FMU in an FMI 3.0 importer and compare the results with your FMI 2.0
FMU, e.g. with FMPy:

```python skip
import fmpy
result = fmpy.simulate_fmu("Integrator.fmu", stop_time=10.0, start_values={"gain": 2.0})
```

## Complete example

**Before**: PythonFMU (FMI 2.0)

```python skip
from pythonfmu import Fmi2Causality, Fmi2Slave, Fmi2Variability, Integer, Real


class Integrator(Fmi2Slave):

    author = "Jane Doe"
    description = "Integrates its input"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.u = 0.0
        self.gain = 1.0
        self.y = 0.0
        self.steps = 0

        self.register_variable(Real("u", causality=Fmi2Causality.input))
        self.register_variable(Real("gain", causality=Fmi2Causality.parameter,
                                    variability=Fmi2Variability.tunable))
        self.register_variable(Real("y", causality=Fmi2Causality.output))
        self.register_variable(Integer("steps", causality=Fmi2Causality.output,
                                       variability=Fmi2Variability.discrete))

    def setup_experiment(self, start_time, stop_time, tolerance):
        self.y = 0.0
        self.steps = 0

    def do_step(self, current_time, step_size):
        self.y += self.gain * self.u * step_size
        self.steps += 1
        return True
```

**After**: PythonFMU3 (FMI 3.0)

```python
from pythonfmu3 import Fmi3Causality, Fmi3Slave, Fmi3Variability, Float64, Int32


class Integrator(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "Jane Doe"                        # was a class attribute
        self.description = "Integrates its input"

        self.time = 0.0                                 # new: the independent variable
        self.u = 0.0
        self.gain = 1.0
        self.y = 0.0
        self.steps = 0

        self.register_variable(Float64("time", causality=Fmi3Causality.independent,
                                       variability=Fmi3Variability.continuous))
        self.register_variable(Float64("u", causality=Fmi3Causality.input, start=0.0))
        self.register_variable(Float64("gain", causality=Fmi3Causality.parameter,
                                       variability=Fmi3Variability.tunable, start=1.0))
        self.register_variable(Float64("y", causality=Fmi3Causality.output))
        self.register_variable(Int32("steps", causality=Fmi3Causality.output,
                                     variability=Fmi3Variability.discrete))

    def enter_initialization_mode(self):              # was setup_experiment
        self.y = 0.0
        self.steps = 0

    def do_step(self, current_time, step_size):
        self.y += self.gain * self.u * step_size
        self.steps += 1
        self.time = current_time + step_size
        return True
```
