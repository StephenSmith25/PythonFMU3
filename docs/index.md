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
- **🔧 Rich Variable Types**: Support for Float64, Int32, Boolean, String, and arrays
- **⚡ High Performance**: Optimized C++ runtime with embedded Python interpreter
- **🌐 Cross-Platform**: Windows, Linux, and macOS support
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
        
        # Register variables
        self.register_variable(Float64("input", causality=Fmi3Causality.input))
        self.register_variable(Float64("output", causality=Fmi3Causality.output))
        
        # Initialize values
        self.input = 0.0
        self.output = 0.0
    
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
```python
import fmpy
result = fmpy.simulate_fmu('MyModel.fmu', stop_time=10.0)
```

The FMU also runs in native FMI 3.0 importers such as OMSimulator, `fmusim` or Simulink.
The simulating machine needs Python 3 with a shared Python library and your model's
packages; see [Running FMUs outside Python](install.md#running-fmus-outside-python-linux-and-macos).

## Architecture

PythonFMU3 uses a hybrid architecture combining the performance of C++ with the flexibility of Python:

- **C++ Runtime**: High-performance FMI interface implementation
- **Embedded Python**: Isolated Python interpreter for model execution
- **Python loader (Linux/macOS)**: the FMU's library has no link-time dependency on
  Python. It uses the host's interpreter when there is one, and otherwise loads
  `libpython` on first instantiation, so native (non-Python) importers can load the FMU
- **Smart Bridging**: Efficient data exchange between C++ and Python
- **Memory Management**: Automatic resource cleanup and garbage collection

This project is a fork of the original PythonFMU repository available at https://github.com/NTNU-IHB/PythonFMU, which was used as the basis for adding support for FMI 3.0. While we have made efforts to expand the functionality of this project, it currently has some limitations and does not support all the features of FMI 3.0. We would like to acknowledge and give credit to the original PythonFMU project for their contributions to this work.

## What's Supported

### FMI 3.0 Features
- ✅ **Co-simulation FMUs** with `do_step()` method
- ✅ **Model Exchange FMUs** with derivative functions
- ✅ **Variable types**: Float64, Int32, UInt64, Boolean, String
- ✅ **Array variables** with dimensions and structural parameters
- ✅ **Parameters** with fixed, tunable, and constant variability
- ✅ **Units and display units** for physical quantities
- ✅ **Initial values** and causality declarations
- ✅ **Event handling** and discrete state updates
- ✅ **State serialization** and deserialization
- ✅ **Logging** and error reporting

### Advanced Capabilities
- ✅ **NumPy integration** for scientific computing
- ✅ **Custom getters/setters** for complex variable access
- ✅ **Nested variables** with structured naming
- ✅ **Resource management** for external files and dependencies
- ✅ **Multi-platform support** (Windows, Linux, macOS)
- ✅ **Memory-efficient** variable handling

### Limitations
- ⚠️ **Binary variables** not yet supported
- ⚠️ **Clock variables** and scheduled execution not implemented
- ⚠️ **Some FMI 3.0 advanced features** are still in development

## Examples and Documentation

Explore comprehensive examples and documentation:

- **[Co-simulation Examples](usage.md)**: PID controllers, filters, state machines
- **[Model Exchange Examples](usageMX.md)**: Van der Pol oscillator, Robertson problem
- **[API Reference](api.md)**: Complete class and method documentation
- **[Installation Guide](install.md)**: Setup instructions for all platforms

## Community and Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/StephenSmith25/PythonFMU3/issues)
- 💡 **Feature Requests**: [GitHub Discussions](https://github.com/StephenSmith25/PythonFMU3/discussions)
- 📖 **Documentation**: [Read the Docs](https://pythonfmu3.readthedocs.io/)
- 📦 **PyPI Package**: [pythonfmu3](https://pypi.org/project/pythonfmu3/)
