from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Float64, Fmi3Initial


class BouncingBall(Fmi3Slave):

    author = "..."
    description = "Bouncing Ball"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
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
