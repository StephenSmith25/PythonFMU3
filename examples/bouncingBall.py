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
