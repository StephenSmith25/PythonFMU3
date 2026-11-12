# PythonFMU3

> A lightweight framework that enables the packaging of Python 3 code as **Co-simulation** and **Model Exchange** FMUs (following FMI version 3.0).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/StephenSmith25/PythonFMU3/issues)

[![CI](https://github.com/StephenSmith25/PythonFMU3/workflows/CI/badge.svg)](https://github.com/StephenSmith25/PythonFMU3/actions?query=workflow%3ACI)
[![PyPI](https://img.shields.io/pypi/v/pythonfmu3)](https://pypi.org/project/pythonfmu3/)
[![Read the Docs](https://readthedocs.org/projects/pythonfmu3/badge/?version=latest)](https://pythonfmu3.readthedocs.io/)

## Overview

PythonFMU3 bridges the gap between Python's rich ecosystem and the Functional Mock-up Interface (FMI) 3.0 standard, enabling seamless integration of Python models into multi-domain simulation environments. Whether you're developing control systems, signal processing algorithms, or complex system models, PythonFMU3 makes it easy to package your Python code as industry-standard FMUs.

### Key Features

- **🔄 Dual FMU Support**: Create both Co-simulation and Model Exchange FMUs
- **🐍 Pure Python**: Write your models in familiar Python syntax
- **📦 Easy Packaging**: Simple CLI tool to build FMUs from Python scripts
- **🔧 Variable Types**: Float64, Int32, Int64, UInt64, Boolean, String and Enumeration, plus NumPy arrays of the numeric types
- **⚡ Native FMU binaries**: a C++ FMI 3.0 implementation that runs your Python code in an embedded interpreter
- **🌐 Cross-Platform**: prebuilt for Windows (x86_64) and Linux (x86_64); macOS and ARM build from source
- **📊 NumPy Integration**: Native support for array operations and scientific computing
- **🎛️ Parameter Management**: Configurable parameters with units and constraints
- **🔍 Debugging Support**: Built-in logging and error handling

### Use Cases

**Control Systems**
- PID controllers, state machines, and adaptive control algorithms
- Integration with Simulink, OpenModelica, or other simulation tools

**Signal Processing**
- Digital filters, signal generators, and data analysis algorithms
- Real-time processing in co-simulation environments

**Machine Learning**
- Deploy trained models as FMUs for system-level simulation
- Integration of AI/ML components in engineering workflows

**System Modeling**
- Battery models, thermal systems, and multi-physics simulations
- Rapid prototyping of mathematical models

## Quick Start

### Installation
```bash
pip install pythonfmu3
```

### Create Your First FMU

**1. Write a Python model:**
```python
from pythonfmu3 import Fmi3Slave, Fmi3Causality, Float64

class MyModel(Fmi3Slave):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Create the attributes first: register_variable only adds a setter
        # (needed for inputs and parameters) for attributes that already exist
        self.input = 0.0
        self.output = 0.0

        # Register variables
        self.register_variable(Float64("input", causality=Fmi3Causality.input, start=0.0))
        self.register_variable(Float64("output", causality=Fmi3Causality.output))
    
    def do_step(self, current_time, step_size):
        # Your model logic here
        self.output = 2.0 * self.input
        return True
```

**2. Build the FMU:**
```bash
pythonfmu3 build -f my_model.py
```

**3. Use in simulation:**
<!-- skip-test -->
```python
import fmpy
result = fmpy.simulate_fmu('MyModel.fmu', stop_time=10.0)
```

The FMU also runs in native FMI 3.0 importers such as OMSimulator, `fmusim` or Simulink.
The simulating machine needs Python 3 with a shared Python library and your model's
packages; see [Running FMUs outside Python](install.md#running-fmus-outside-python-linux-and-macos).

## Architecture

An FMU built by PythonFMU3 contains your script, a copy of the `pythonfmu3` package and a
native library implementing the FMI 3.0 C API:

- **C++ wrapper**: implements the FMI functions and forwards each call to your Python
  class (`do_step`, the variable getters and setters, ...)
- **Python interpreter**: the host's interpreter when the importer is itself Python (e.g.
  FMPy), otherwise one started inside the simulation process. Your model's packages must
  be installed in that Python; see [Dependencies](dependencies.md)
- **Python loader (Linux/macOS)**: the FMU's library has no link-time dependency on
  Python, and loads `libpython` on first instantiation when the host has none, so native
  (non-Python) importers can load the FMU

This project is a fork of the original PythonFMU repository available at https://github.com/NTNU-IHB/PythonFMU, which was used as the basis for adding support for FMI 3.0. While we have made efforts to expand the functionality of this project, it currently has some limitations and does not support all the features of FMI 3.0. We would like to acknowledge and give credit to the original PythonFMU project for their contributions to this work.

## What's Supported

### FMI 3.0 Features
- ✅ **Co-simulation FMUs** with `do_step()` method
- ✅ **Model Exchange FMUs** with derivative functions
- ✅ **Variable types**: Float64, Int32, Int64, UInt64, Boolean, String, Enumeration
- ✅ **Array variables** (NumPy) of the numeric and Boolean types, with fixed sizes or
  sizes given by a structural parameter
- ✅ **Parameters** with fixed, tunable, and constant variability
- ✅ **Units** for physical quantities
- ✅ **Initial values** and causality declarations
- ✅ **Event indicators** and discrete state updates (Model Exchange)
- ✅ **Getting, setting and serializing FMU state** (opt-in with `--handle-state` and
  `--serialize-state`; see the limitations below)
- ✅ **Logging**, with Python exceptions reported with their traceback

### Advanced Capabilities
- ✅ **NumPy integration** for scientific computing
- ✅ **Custom getters/setters** for complex variable access
- ✅ **Nested variables** with structured naming
- ✅ **Resource management** for external files and dependencies
- ✅ **Runs in any FMI 3.0 importer**: Python-based (FMPy) and native (OMSimulator,
  `fmusim`, Simulink, ...)
- ✅ **Memory-efficient** variable handling

### Limitations
- ⚠️ **Variable types** Float32, Int8, Int16, UInt8, UInt16, UInt32, Binary and Clock are not
  supported, nor are String arrays
- ⚠️ **Scheduled Execution** is not supported, and Co-simulation ignores Event Mode and
  early return
- ⚠️ **Directional and adjoint derivatives** are not available
- ⚠️ **Array sizes** are fixed once the FMU is instantiated: changing a structural
  parameter in Configuration Mode does not resize arrays
- ⚠️ **FMU state** only covers registered variables, and serialization uses JSON (no NumPy
  arrays). Override `_get_fmu_state`/`_set_fmu_state` if your model has other internal state
- ⚠️ **Prebuilt binaries** exist for Windows x86_64 and Linux x86_64 only; on macOS and ARM,
  build the wrapper from source (see [Installation](install.md))

## Examples and Documentation

Explore comprehensive examples and documentation:

- **[Co-simulation Examples](usage.md)**: PID controller, units, arrays, step results
- **[Model Exchange Examples](usageMX.md)**: Van der Pol oscillator, bouncing ball with events
- **[Installation Guide](install.md)**: installing, building from source, and running FMUs
  outside Python
- **[Dependencies](dependencies.md)**: third-party packages and which Python an FMU uses
- **[Changelog](changelog.md)**

## Community and Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/StephenSmith25/PythonFMU3/issues)
- 💡 **Feature Requests**: [GitHub Issues](https://github.com/StephenSmith25/PythonFMU3/issues)
- 📖 **Documentation**: [Read the Docs](https://pythonfmu3.readthedocs.io/)
- 📦 **PyPI Package**: [pythonfmu3](https://pypi.org/project/pythonfmu3/)
