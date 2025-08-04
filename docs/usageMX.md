# Model Exchange Examples

Model Exchange FMUs are used for continuous-time simulation where an external solver integrates the system of differential equations. The FMU provides the derivative function and state information, while the master algorithm handles time stepping and numerical integration.

## Key Concepts

### Model Exchange vs Co-Simulation
- **Model Exchange**: External solver calls your derivative function at each integration step
- **Co-Simulation**: Your FMU manages its own time stepping with `do_step()`

### Required Methods
For Model Exchange FMUs, you must implement:
- `get_continuous_state_derivatives()`: Returns derivatives of continuous states
- `get_nominals_of_continuous_states()`: Returns nominal values for scaling
- Optional: `get_event_indicators()`, `update_discrete_states()`



## Key Implementation Details

### Variable Registration
Model Exchange FMUs require specific variable declarations:

```python skip
# Independent variable (time)
self.register_variable(Float64("time", 
                              causality=Fmi3Causality.independent, 
                              variability=Fmi3Variability.continuous))

# States with initial values
self.register_variable(Float64("x0", 
                              causality=Fmi3Causality.output,
                              start=2.0,                    # Initial value
                              variability=Fmi3Variability.continuous,
                              initial=Fmi3Initial.exact))   # Must be exact

# Derivatives (local variables)
self.register_variable(Float64("derx0", 
                              causality=Fmi3Causality.local,
                              variability=Fmi3Variability.continuous,
                              derivative=1))                # Derivative of variable 1 (x0)
```

### Derivative Function
The core of Model Exchange is the derivative function:

```python
def get_continuous_state_derivatives(self):
    """Calculate derivatives of continuous states"""
    # Van der Pol oscillator equations:
    # dx0/dt = x1
    # dx1/dt = μ(1-x0²)x1 - x0
    
    self.derx0 = self.x1
    self.derx1 = self.mu * ((1 - self.x0**2) * self.x1) - self.x0
    
    return [self.derx0, self.derx1]
```

## Example

```python

from pythonfmu3 import Fmi3Causality, ModelExchange, Fmi3Variability, Fmi3SlaveBase, Fmi3Status, Float64, Fmi3Initial, Unit, Float64Type, Fmi3StepResult

from typing import List

class VanDerPol(Fmi3SlaveBase, ModelExchange):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = ""
        self.description = "Van Der Pol oscillator problem for model exchange FMUs"

        self.time = 0.0
        self.mu = 1.0
        self.x0 = 2
        self.x1 = 0
        self.derx0 = 0.0
        self.derx1 = 0.0

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("x0", causality=Fmi3Causality.output, start=2, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact))
        self.register_variable(Float64("x1", causality=Fmi3Causality.output, start=0, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact))
        self.register_variable(Float64("derx0", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=1))
        self.register_variable(Float64("derx1", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=2))
        self.register_variable(Float64("mu", causality=Fmi3Causality.parameter, variability=Fmi3Variability.fixed))


    def get_continuous_state_derivatives(self) -> List[float]:
        self.derx0 = self.x1
        self.derx1 = self.mu * ((1 - self.x0**2) * self.x1) - self.x0
        return [self.derx0, self.derx1]
       
    def get_nominals_of_continuous_states(self, nStates: int) -> List[float]:
        return [1.0, 1.0]

```


## Build the FMU

Once your Python script is ready, build the FMU:

```bash
# Using the CLI
pythonfmu3 build -f van_der_pol.py
```

## Usage Example

The generated FMU can be used with any FMI-compatible tool:

```python skip
# Example with FMPy
import fmpy

# Load and simulate the FMU
fmu_filename = "VanDerPol.fmu"
result = fmpy.simulate_fmu(
    fmu_filename,
    stop_time=20.0,
    step_size=0.01,
    start_values={'mu': 1.0, 'x0': 2.0, 'x1': 0.0}
)

# Plot results
import matplotlib.pyplot as plt
plt.plot(result['time'], result['x0'], label='x0')
plt.plot(result['time'], result['x1'], label='x1')
plt.xlabel('Time')
plt.ylabel('State Values')
plt.legend()
plt.grid(True)
plt.show()
```

## Advanced Features

### Event Handling
For systems with discrete events. Firstly, mark the event indicators in register variable with `has_event_indicator`,

```python skip
self.register_variable(Float64("h", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact), has_event_indicator=True)
```

Then define the event methods, `get_event_indicators()` and `update_discrete_states`.

```python skip
def get_event_indicators(self):
    return [0.2]

def update_discrete_states(self):
    """Handle discrete state updates after events"""
    fdsr = Fmi3UpdateDiscreteStatesResult()
    fdsr.valuesOfContinuousStatesChanged = True
```


### Example

```python
from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3SlaveBase, ModelExchange, Float64, Fmi3Initial, Fmi3UpdateDiscreteStatesResult

from typing import List

import sys

EVENT_EPS = 1e-12

class BouncingBall(Fmi3SlaveBase, ModelExchange):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "..."
        self.description = "Bouncing Ball"

        self.time = 0.0
        self.h = 1.0
        self.v = 0.0
        self.derh = 0.0
        self.derv = 0.0
        self.g = -9.81
        self.e = 0.7
        self.v_min = 0.1

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))

        self.register_variable(Float64("h", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact),
                                has_event_indicator=True)
        self.register_variable(Float64("derh", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=1))
        self.register_variable(Float64("v", causality=Fmi3Causality.output, start=0, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact))
        self.register_variable(Float64("derv", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=3))

        self.register_variable(Float64("g", causality=Fmi3Causality.parameter, variability=Fmi3Variability.fixed))
        self.register_variable(Float64("e", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable))
        self.register_variable(Float64("v_min", variability=Fmi3Variability.constant, start=0.1))
        


    def get_continuous_state_derivatives(self) -> List[float]:
        self.derh = self.v
        self.derv = self.g
        return [self.derh, self.derv]
        
    def get_event_indicators(self) -> List[float]:
        z = [self.h]
        if self.h > -EVENT_EPS and self.h <=0 and self.v > 0:
            z[0] = -EVENT_EPS

        return z
    
    def update_discrete_states(self):
        fdsr = Fmi3UpdateDiscreteStatesResult()

        if self.h <= 0 and self.v < 0:
            self.h = sys.float_info.min
            self.v = -self.v * self.e
            
            if self.v < self.v_min:
                self.v = 0.0;
                self.g = 0.0;
            
            fdsr.valuesOfContinuousStatesChanged = True

        return fdsr




```

## Build the FMU

Once your Python script is ready, build the FMU:

```bash
# Using the CLI
pythonfmu3 build -f bouncing_ball.py
```

{% raw %}
<!-- This will be hidden in MkDocs -->
```python
VanDerPol(instance_name="dummy")
BouncingBall(instance_name="dummy")
```
{% endraw %}
```