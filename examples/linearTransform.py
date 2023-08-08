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
        
        self.B = np.ndarray(shape=(self.m, self.n), dtype=float) 
        self.B = np.reshape([1.0, 1.0, 2.0, 1.0], newshape=self.B.shape)

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
