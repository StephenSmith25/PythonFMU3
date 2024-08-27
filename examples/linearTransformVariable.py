from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Float64, UInt64, Fmi3Initial, Dimension
import numpy as np


class LinearTransformVariable(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "..."
        self.description = "Linear transform with variable sized arrays"

        self.time = 0.0

        self.m = 2
        self.n = 2

        self.scalar = 2.00

        self.u = np.array([1.0, 2.0]).reshape((self.m, 1))
        self.offset = np.array([1.0, 2.0]).reshape((self.m, 1))
        self.A = np.array([1.0, 1.0, 2.0, 1.0]).reshape((self.m, self.n))
        self.y = np.array([0.0, 0.0]).reshape((self.n, 1))


        # 0
        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        # 1
        self.register_variable(UInt64("m", causality=Fmi3Causality.structuralParameter, variability=Fmi3Variability.tunable, start=2, setter=lambda v: self.structual_parameter_setter_m(v)))
        # 2
        self.register_variable(UInt64("n", causality=Fmi3Causality.structuralParameter, variability=Fmi3Variability.tunable, start=2, setter=lambda v: self.structual_parameter_setter_n(v)))
        # 3
        self.register_variable(Float64("scalar", causality=Fmi3Causality.input, start=2.0))
        # 4
        self.register_variable(Float64("u", causality=Fmi3Causality.input, dimensions=[Dimension(valueReference="2")]))
        # 5
        self.register_variable(Float64("offset", causality=Fmi3Causality.input, dimensions=[Dimension(valueReference="1")]))
        # 6
        self.register_variable(Float64("A", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable, dimensions=[Dimension(valueReference="1"), Dimension(valueReference="2")]))
        # 7
        self.register_variable(Float64("y", causality=Fmi3Causality.output, dimensions=[Dimension(valueReference="1")]))
    
    def structual_parameter_setter_m(self, value):
        self.m = value
        self.offset = np.resize(self.offset, self.m)
        self.A = np.resize(self.A, (self.m, self.n))
    
    def structual_parameter_setter_n(self, value):
        self.n = value
        self.y = np.resize(self.y, self.n)
        self.u = np.resize(self.u, self.n)
        self.A = np.resize(self.A, (self.m, self.n))

    def do_step(self, current_time, step_size):
        self.y = self.scalar*self.A.dot(self.u) + self.offset
        return True
