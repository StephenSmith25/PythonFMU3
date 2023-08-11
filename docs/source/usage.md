# Examples

## Write the script

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
The bouncing ball example from the reference fmus repository may be created with,


```python
from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Real, Fmi3Initial

class BouncingBall(Fmi3Slave):

    author = "..."
    description = "Bouncing Ball"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.counter = 0
        self.h = 1.0
        self.derh = 0.0
        self.v = 0.0
        self.derh = 0.0
        self.derv = 0.0
        self.g = -9.81
        self.e = 0.7
        self.v_min = 0.1
    
        
        self.register_variable(Real("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))

        self.register_variable(Real("h", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact))
        self.register_variable(Real("derh", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=1))
        self.register_variable(Real("v", causality=Fmi3Causality.output, start=0, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact))
        self.register_variable(Real("derv", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=3))

        self.register_variable(Real("g", causality=Fmi3Causality.parameter, variability=Fmi3Variability.fixed))
        self.register_variable(Real("e", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable))
        self.register_variable(Real("v_min", variability=Fmi3Variability.constant, start=0.1))

    def do_step(self, current_time, step_size):
        self.derv = self.g
        self.derh = self.v
        self.h += self.derh * step_size
        self.v += self.derv * step_size

        if self.h <= 0 and self.v < 0:
            self.h = 1e-12
            self.v = -self.v*self.e
            if self.v < self.v_min:
                self.v = 0
                self.g = 0
        return True

```

If numpy is installed, arrays may be used with,

```python
from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Real, UInt64, Fmi3Initial, Dimension
import numpy as np


class LinearTransform(Fmi3Slave):

    author = "..."
    description = "LinearTransform"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.m = 2
        self.n = 2

        self.scalar = 2.00

        self.u = np.ndarray(shape=(self.m, 1), dtype=float) 
        self.u = np.reshape([1.0, 2.0], newshape=self.u.shape)
        
        self.offset = np.ndarray(shape=(self.m, 1), dtype=float) 
        self.offset = np.reshape([1.0, 2.0], newshape=self.offset.shape)

        self.A = np.ndarray(shape=(self.m, self.n), dtype=float) 
        self.A = np.reshape([1.0, 1.0, 2.0, 1.0], newshape=self.A.shape)
        
        self.y = np.ndarray(shape=(self.m, 1), dtype=float) 
        self.y = np.reshape([0.0, 0.0], newshape=self.y.shape)

        
        self.register_variable(Real("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(UInt64("m", causality=Fmi3Causality.structuralParameter, variability=Fmi3Variability.tunable, start=2))
        self.register_variable(Real("scalar", causality=Fmi3Causality.input, start=2.0))
        self.register_variable(Real("u", causality=Fmi3Causality.input, dimensions=[Dimension(valueReference="1")]))
        self.register_variable(Real("offset", causality=Fmi3Causality.input, dimensions=[Dimension(start=f"{self.m}")]))
        self.register_variable(Real("A", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable, dimensions=[Dimension(start=f"{self.m}"), Dimension(start=f"{self.n}")]))
        self.register_variable(Real("y", causality=Fmi3Causality.output, dimensions=[Dimension(valueReference="1")]))

    def do_step(self, current_time, step_size):
        self.y = self.scalar*self.A.dot(self.u) + self.offset
        return True
```

### Create the FMU

```bash 
    pythonfmu3 build -f pythonslave.py myproject
```

In this example a python class named `PythonSlave` that extends `Fmi3Slave` is declared in a file named `pythonslave.py`,
where `myproject` is an optional folder containing additional project files required by the python script.
Project folders such as this will be recursively copied into the FMU. Multiple project files/folders may be added.