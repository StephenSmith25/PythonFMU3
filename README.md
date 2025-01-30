# PythonFMU3

> A lightweight framework that enables the packaging of Python 3 code as co-simulation FMUs (following FMI version 3.0).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/StephenSmith25/PythonFMU3/issues)

[![CI](https://github.com/StephenSmith25/PythonFMU3/workflows/CI/badge.svg)](https://github.com/StephenSmith25/PythonFMU3/actions?query=workflow%3ACI)
[![PyPI](https://img.shields.io/pypi/v/pythonfmu3)](https://pypi.org/project/pythonfmu3/)
[![Read the Docs](https://readthedocs.org/projects/pythonfmu3/badge/?version=latest)](https://pythonfmu3.readthedocs.io/)


This project is a fork of the original PythonFMU repository available at https://github.com/NTNU-IHB/PythonFMU, which was used as the basis for adding support for FMI 3.0. While we have made efforts to expand the functionality of this project, it currently has some limitations and does not support all the features of FMI 3.0. We would like to acknowledge and give credit to the original PythonFMU project for their contributions to this work.

### Support:

Please take a look at the examples to see the supported features.

### Future

In no particular order, we plan to add support for:

- Support more variable types from FMI3
- Improve array support
- Add event mode

### How do I build an FMU from python code?

1. Install `pythonfmu3` package:

```bash
pip install pythonfmu3
```

2. Create a new class extending the `Fmi3Slave` class declared in the `pythonfmu3.fmi3slave` module (see below for an example).
3. Run `pythonfmu3 build` to create the fmu.

```
usage: pythonfmu3 build [-h] -f SCRIPT_FILE [-d DEST] [--doc DOCUMENTATION_FOLDER] [--terminals TERMINALS_FOLDER] [--no-external-tool]
                       [--no-variable-step] [--interpolate-inputs] [--only-one-per-process] [--handle-state]
                       [--serialize-state] [--use-memory-management]
                       [Project files [Project files ...]]

Build an FMU from a Python script.

positional arguments:
  Project files         Additional project files required by the Python script.

optional arguments:
  -h, --help            show this help message and exit
  -f SCRIPT_FILE, --file SCRIPT_FILE
                        Path to the Python script.
  -d DEST, --dest DEST  Where to save the FMU.
  --doc DOCUMENTATION_FOLDER
                        Documentation folder to include in the FMU.
  --terminals TERMINALS_FOLDER
                        Folder of terminals to include in the FMU.
  --no-external-tool    If given, needsExecutionTool=false
  --no-variable-step    If given, canHandleVariableCommunicationStepSize=false
  --interpolate-inputs  If given, canInterpolateInputs=true
  --only-one-per-process
                        If given, canBeInstantiatedOnlyOncePerProcess=true
  --handle-state        If given, canGetAndSetFMUstate=true
  --serialize-state     If given, canSerializeFMUstate=true
```

### How do I build an FMU from python code with third-party dependencies?

Often, Python scripts depends on non-builtin libraries like `numpy`, `scipy`, etc.
_PythonFMU_ does not package a full environment within the FMU.
However, you can package a `requirements.txt` or `environment.yml` file within your FMU following these steps:

1. Install _pythonfmu_ package: `pip install pythonfmu3`
2. Create a new class extending the `Fmi3Slave` class declared in the `pythonfmu3.fmi3slave` module (see below for an example).
3. Create a `requirements.txt` file (to use _pip_ manager) and/or a `environment.yml` file (to use _conda_ manager) that defines your dependencies.
4. Run `pythonfmu3 build -f myscript.py requirements.txt` to create the fmu including the dependencies file.

And using `pythonfmu3 deploy`, end users will be able to update their local Python environment. The steps to achieve that:

1. Install _pythonfmu_ package: `pip install pythonfmu3`
2. Be sure to be in the Python environment to be updated. Then execute `pythonfmu3 deploy -f my.fmu`

```
usage: pythonfmu3 deploy [-h] -f FMU [-e ENVIRONMENT] [{pip,conda}]

Deploy a Python FMU. The command will look in the `resources` folder for one of the following files:
`requirements.txt` or `environment.yml`. If you specify a environment file but no package manager, `conda` will be selected for `.yaml` and `.yml` otherwise `pip` will be used. The tool assume the Python environment in which the FMU should be executed is the current one.

positional arguments:
  {pip,conda}           Python packages manager

optional arguments:
  -h, --help            show this help message and exit
  -f FMU, --file FMU    Path to the Python FMU.
  -e ENVIRONMENT, --env ENVIRONMENT
                        Requirements or environment file.
```

### Example:

#### Write the script

```python

from pythonfmu3 import Fmi3Causality, Fmi3Slave, Boolean, Int32, Float64, String


class PythonSlave(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "John Doe"
        self.description = "A simple description"

        self.time = 0.0
        self.intOut = 1
        self.realOut = 3.0
        self.booleanVariable = True
        self.stringVariable = "Hello World!"
        self.register_variable(Float64("time", causality=Fmi3Causality.independent))
        self.register_variable(Int32("intOut", causality=Fmi3Causality.output))
        self.register_variable(Float64("realOut", causality=Fmi3Causality.output))
        self.register_variable(Boolean("booleanVariable", causality=Fmi3Causality.local))
        self.register_variable(String("stringVariable", causality=Fmi3Causality.local))
        
        # Note:
        # it is also possible to explicitly define getters and setters as lambdas in case the variable is not backed by a Python field.
        # self.register_variable(Float64("myReal", causality=Fmi3Causality.output, getter=lambda: self.realOut, setter=lambda v: set_real_out(v))

    def do_step(self, current_time, step_size):
        return True

```

#### Create the FMU

```
pythonfmu3 build -f pythonslave.py myproject
```

In this example a python class named `PythonSlave` that extends `Fmi3Slave` is declared in a file named `pythonslave.py`,
where `myproject` is an optional folder containing additional project files required by the python script.
Project folders such as this will be recursively copied into the FMU. Multiple project files/folders may be added.
