# Examples

## Write the script

```python
from pythonfmu3 import Fmi3Causality, Fmi3Slave, Boolean, Int32, Float64, String


class PythonSlave(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.author = "John Doe"
        self.description = "A simple description"

        self.intOut = 1
        self.realOut = 3.0
        self.booleanVariable = True
        self.stringVariable = "Hello World!"
        self.register_variable(Int32("intOut", causality=Fmi3Causality.output))
        self.register_variable(Float64("realOut", causality=Fmi3Causality.output))
        self.register_variable(Boolean("booleanVariable", causality=Fmi3Causality.local))
        self.register_variable(String("stringVariable", causality=Fmi3Causality.local))
        
        # Note:
        # it is also possible to explicitly define getters and setters as lambdas in case the variable is not backed by a Python field.
        # self.register_variable(Float64("myReal", causality=Fmi3Causality.output, getter=lambda: self.realOut, setter=lambda v: set_float64_out(v))

    def do_step(self, current_time, step_size):
        return True

```
The bouncing ball example from the reference fmus repository may be created with,


```python
from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Float64, Fmi3Initial

class BouncingBall(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.author = ".."
        self.description="Bouncing Ball" 

        self.time = 0.0
        self.counter = 0
        self.h = 1.0
        self.derh = 0.0
        self.v = 0.0
        self.derh = 0.0
        self.derv = 0.0
        self.g = -9.81
        self.e = 0.7
        self.v_min = 0.1
    
        
        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))

        self.register_variable(Float64("ball.h", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact), nested=False)
        self.register_variable(Float64("ball.derh", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=1), nested=False)
        self.register_variable(Float64("ball.v", causality=Fmi3Causality.output, start=0, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact), nested=False)
        self.register_variable(Float64("ball.derv", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=3), nested=False)

        self.register_variable(Float64("g", causality=Fmi3Causality.parameter, variability=Fmi3Variability.fixed))
        self.register_variable(Float64("e", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable))
        self.register_variable(Float64("v_min", variability=Fmi3Variability.constant, start=0.1))

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

Units can be added to this example through the `Unit` class,

```python
from pythonfmu3 import Unit
velocity_unit =  Unit(name="m/s", m=1, s=-1)
```
In order to use this definition, a variable type will be required,
```python
from pythonfmu3 import Float64Type
var_type = Float64Type(name="Velocity", unit=velocity_unit.name quantity = "Velocity")
```
which can now be utilized in the register variables call,
```
velocity_unit =  Unit(name="m/s", m=1, s=-1)
self.add_units([velocity_unit])
var_type = Float64Type(name="Velocity", unit=velocity_unit.name quantity = "Velocity")
self.register_variable(Float64(".v", causality=Fmi3Causality.output, start=0, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact), var_type=var_type)
```

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

        self.u = np.ndarray(shape=(self.m, 1), dtype=float) 
        self.u = np.reshape([1.0, 2.0], newshape=self.u.shape)
        
        self.offset = np.ndarray(shape=(self.m, 1), dtype=float) 
        self.offset = np.reshape([1.0, 2.0], newshape=self.offset.shape)

        self.A = np.ndarray(shape=(self.m, self.n), dtype=float) 
        self.A = np.reshape([1.0, 1.0, 2.0, 1.0], newshape=self.A.shape)
        
        self.y = np.ndarray(shape=(self.m, 1), dtype=float) 
        self.y = np.reshape([0.0, 0.0], newshape=self.y.shape)

        
        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(UInt64("m", causality=Fmi3Causality.structuralParameter, variability=Fmi3Variability.tunable, start=2))
        self.register_variable(Float64("scalar", causality=Fmi3Causality.input, start=2.0))
        self.register_variable(Float64("u", causality=Fmi3Causality.input, dimensions=[Dimension(valueReference="1")]))
        self.register_variable(Float64("offset", causality=Fmi3Causality.input, dimensions=[Dimension(start=f"{self.m}")]))
        self.register_variable(Float64("A", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable, dimensions=[Dimension(start=f"{self.m}"), Dimension(start=f"{self.n}")]))
        self.register_variable(Float64("y", causality=Fmi3Causality.output, dimensions=[Dimension(valueReference="1")]))

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
