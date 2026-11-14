"""A data-driven surrogate: a NumPy polynomial fitted to samples, exposed as an FMU.

Replace the fit with your own model (scikit-learn, PyTorch, ...): load it in __init__
(put the file next to this script and pass it as a project file when building) and call
it in do_step.
"""
import numpy as np

from pythonfmu3 import Fmi3Causality, Fmi3Slave, Fmi3Variability, Float64


class Surrogate(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.author = "PythonFMU3 Studio template"
        self.description = "Polynomial surrogate of y = sin(x) * exp(-x / 5) on [0, 10]"

        x = np.linspace(0.0, 10.0, 200)                       # "training data"
        self._coeffs = np.polyfit(x, np.sin(x) * np.exp(-x / 5.0), deg=9)

        self.time = 0.0
        self.x = 0.0
        self.y = float(np.polyval(self._coeffs, self.x))
        self.speed = 1.0

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("x", causality=Fmi3Causality.output))
        self.register_variable(Float64("y", causality=Fmi3Causality.output))
        self.register_variable(Float64("speed", causality=Fmi3Causality.parameter,
                                       variability=Fmi3Variability.tunable, start=1.0))

    def do_step(self, current_time, step_size):
        self.time = current_time + step_size
        self.x = (self.speed * self.time) % 10.0              # sweep the input range
        self.y = float(np.polyval(self._coeffs, self.x))
        return True
