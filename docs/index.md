# PythonFMU3

> A lightweight framework that enables the packaging of Python 3 code as **Co-simulation** and **Model Exchange** FMUs (following FMI version 3.0).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/StephenSmith25/PythonFMU3/issues)

[![CI](https://github.com/StephenSmith25/PythonFMU3/workflows/CI/badge.svg)](https://github.com/StephenSmith25/PythonFMU3/actions?query=workflow%3ACI)
[![PyPI](https://img.shields.io/pypi/v/pythonfmu3)](https://pypi.org/project/pythonfmu3/)
[![Read the Docs](https://readthedocs.org/projects/pythonfmu3/badge/?version=latest)](https://pythonfmu3.readthedocs.io/)

## Overview

PythonFMU3 turns a Python class into an FMI 3.0 FMU (Functional Mock-up Unit): a
standard package that simulation tools such as Simulink, OMSimulator, FMPy and
`fmusim` can import and run alongside their own models. Write the model in Python, with
any packages you like, and PythonFMU3 builds the FMU around it.

Typical uses:

- **Controllers and logic:** PID loops, state machines, supervisory control.
- **Models that are easier to write in Python:** data-driven or machine-learning models,
  models that call scientific libraries, quick prototypes of physics.
- **Signal processing and test inputs:** filters, signal generators, data playback.

## Quick start

```bash
pip install pythonfmu3
```

**1. Write the model** in a file, `my_model.py`:

```python
from pythonfmu3 import Fmi3Causality, Fmi3Slave, Fmi3Variability, Float64


class MyModel(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.description = "Doubles its input"

        # 1. Create every attribute first...
        self.time = 0.0
        self.input = 0.0
        self.output = 0.0

        # 2. ...then register it as an FMU variable (the name is the attribute name)
        self.register_variable(Float64("time", causality=Fmi3Causality.independent,
                                       variability=Fmi3Variability.continuous))
        self.register_variable(Float64("input", causality=Fmi3Causality.input, start=0.0))
        self.register_variable(Float64("output", causality=Fmi3Causality.output))

    def do_step(self, current_time, step_size):
        # Called by the importer to advance the model from current_time by step_size
        self.output = 2.0 * self.input
        self.time = current_time + step_size
        return True
```

Two rules catch most first-time problems:

- **Register a `time` variable** (causality `independent`) and keep `self.time` up to
  date. FMI 3.0 expects every FMU to declare its independent variable.
- **Create each attribute before registering it.** `register_variable` only creates a
  setter for attributes that already exist, and without a setter the importer can't set
  your inputs and parameters.

**2. Build the FMU:**

```bash
pythonfmu3 build -f my_model.py          # writes MyModel.fmu
```

**3. Simulate it** in any FMI 3.0 importer, for example FMPy:

<!-- skip-test -->
```python
import fmpy
result = fmpy.simulate_fmu("MyModel.fmu", stop_time=10.0, start_values={"input": 1.5})
```

The machine that runs the FMU needs Python 3 with a shared Python library, plus the
packages your model imports; see
[Running FMUs outside Python](install.md#running-fmus-outside-python-linux-and-macos) and
[Dependencies](dependencies.md).

Prefer not to install anything yet? [Try PythonFMU3 in your browser](https://stephensmith25.github.io/pythonfmu3-app/):
the web version has the editor and simulator, an AI assistant that writes and tests models,
and shareable links.

## How it works

An FMU built by PythonFMU3 is a zip file containing:

- **your script** and a copy of the `pythonfmu3` package, in `resources/`;
- **`modelDescription.xml`**, generated from the variables you registered;
- **a native library** for each platform, implementing the FMI 3.0 C API. It starts (or
  reuses) a Python interpreter and forwards every FMI call to your class: `fmi3DoStep`
  calls `do_step`, `fmi3GetFloat64` reads your attributes, and so on.

When the importer is itself Python (FMPy, for example), the FMU uses that interpreter.
Otherwise (Simulink, OMSimulator, `fmusim`, ...) the FMU loads a Python installation
itself; on Linux and macOS it looks for `libpython` in several places, and you can point it
at a specific one with `PYTHONFMU_PYTHON_LIBRARY`.

PythonFMU3 is listed on the [FMI tools page](https://fmi-standard.org/tools/).

PythonFMU3 is a fork of [PythonFMU](https://github.com/NTNU-IHB/PythonFMU), which supports
FMI 2.0, extended to FMI 3.0. Many thanks to the PythonFMU authors. Moving a PythonFMU
model across? See [Migrating from PythonFMU](migration.md).

## What's supported

**Interfaces:** Co-Simulation (you implement `do_step`) and Model Exchange (you provide
derivatives and the importer's solver integrates them), or both in one FMU.

**Variables:**

- Float64, Int32, Int64, UInt64, Boolean, String and Enumeration;
- NumPy arrays of the numeric and Boolean types, with fixed sizes or sizes set by a
  structural parameter;
- every causality (parameter, calculated parameter, structural parameter, input, output,
  local, independent) and variability; units; start values and `initial`; custom getters
  and setters; structured names such as `ball.h`.

**Behaviour:**

- events in Model Exchange: event indicators and discrete-state updates;
- step results in Co-Simulation (`Fmi3StepResult`: discard a step, ask to terminate);
- getting, setting and serializing FMU state, opt-in with the `--handle-state` and
  `--serialize-state` build options;
- logging to the importer, with Python exceptions reported with their traceback;
- extra files (data, trained models, `requirements.txt`) packed into the FMU.

**Tools around it:** [PythonFMU3 Studio](studio.md) (a local app, plus a
[web version](https://stephensmith25.github.io/pythonfmu3-app/) with an AI assistant),
[Jupyter notebooks](notebooks.md), and an [MCP server for AI agents](mcp.md).

### Limitations

- **Variable types:** Float32, Int8, Int16, UInt8, UInt16, UInt32, Binary and Clock aren't
  supported, nor are String arrays.
- **Co-Simulation:** Event Mode and early return aren't supported yet, nor is Scheduled
  Execution.
- **Directional and adjoint derivatives** aren't available.
- **Arrays sized by a structural parameter** aren't resized automatically when the
  parameter changes in Configuration Mode. Make the parameter a property whose setter
  reallocates the arrays, as in the
  [pipe CHT example](https://github.com/StephenSmith25/PythonFMU3/tree/HEAD/examples/pipe_cht).
- **FMU state** covers registered variables only, and serialization uses JSON (no NumPy
  arrays). Override `_get_fmu_state` and `_set_fmu_state` if your model has other
  internal state.
- **Prebuilt binaries** are included for Windows x86_64 and Linux x86_64. On macOS and ARM
  Linux, build the native library from source (see [Installation](install.md)).
- **Python is needed on the machine that runs the FMU.**

## Where next

- [Installation](install.md): installing, building from source, and running FMUs outside Python
- [Co-Simulation](usage.md): variables explained, the FMU lifecycle, a PID controller, arrays, building
- [Model Exchange](usageMX.md): states, derivatives and events
- [Dependencies](dependencies.md): third-party packages, and which Python an FMU uses
- [Studio](studio.md), [Jupyter notebooks](notebooks.md) and [AI agents (MCP)](mcp.md)
- [Examples](https://github.com/StephenSmith25/PythonFMU3/tree/HEAD/examples), and the tools each was tested with
- [Changelog](changelog.md)

## Community and support

- Bugs and feature requests: [GitHub Issues](https://github.com/StephenSmith25/PythonFMU3/issues)
- Package: [pythonfmu3 on PyPI](https://pypi.org/project/pythonfmu3/)
