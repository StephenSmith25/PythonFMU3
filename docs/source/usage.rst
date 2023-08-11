Examples
========

#### Write the script

```python

from pythonfmu3 import Fmi3Causality, Fmi3Slave, Boolean, Integer, Real, String


class PythonSlave(Fmi3Slave):

    author = "John Doe"
    description = "A simple description"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.intOut = 1
        self.realOut = 3.0
        self.booleanVariable = True
        self.stringVariable = "Hello World!"
        self.register_variable(Integer("intOut", causality=Fmi3Causality.output))
        self.register_variable(Real("realOut", causality=Fmi3Causality.output))
        self.register_variable(Boolean("booleanVariable", causality=Fmi3Causality.local))
        self.register_variable(String("stringVariable", causality=Fmi3Causality.local))
        
        # Note:
        # it is also possible to explicitly define getters and setters as lambdas in case the variable is not backed by a Python field.
        # self.register_variable(Real("myReal", causality=Fmi3Causality.output, getter=lambda: self.realOut, setter=lambda v: set_real_out(v))

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
