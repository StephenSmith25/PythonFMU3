from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Float64, UInt64, Fmi3Initial, Dimension
import numpy as np


class LinearTransformFixed(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "..."
        self.description = "Linear transform with fixed size matrix/vector"

        self.time = 0.0

        self.m = 2
        self.n = 2

        self.scalar = 2.00

        self.u = np.array([1.0, 2.0]).reshape((self.m, 1))
        self.offset = np.array([1.0, 2.0]).reshape((self.m, 1))
        self.A = np.array([1.0, 1.0, 2.0, 1.0]).reshape((self.m, self.n))
        self.y = np.array([0.0, 0.0]).reshape((self.n, 1))


        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("scalar", causality=Fmi3Causality.input, start=2.0))
        self.register_variable(Float64("u", causality=Fmi3Causality.input, dimensions=[Dimension(start="2")]))
        self.register_variable(Float64("offset", causality=Fmi3Causality.input, dimensions=[Dimension(start="2")]))
        self.register_variable(Float64("A", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable, dimensions=[Dimension(start="2"), Dimension(start="2")]))
        self.register_variable(Float64("y", causality=Fmi3Causality.output, dimensions=[Dimension(start="2")]))
    

    def do_step(self, current_time, step_size):
        self.y = self.scalar*self.A.dot(self.u) + self.offset
        return True
