from pythonfmu import Fmi2Causality, Fmi2Variability, Fmi2Slave, Real, Fmi2Initial


class BouncingBall(Fmi2Slave):

    author = "John Doe"
    description = "A simple description"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.counter = 0
        self.h = 1
        self.derh = 0
        self.v = 0
        self.derh = 0
        self.derv = 0
        self.g = -9.81
        self.e = 0.7
        self.v_min = 0.1
      
        
        self.register_variable(Real("time", causality=Fmi2Causality.independent, variability=Fmi2Variability.continuous))

        self.register_variable(Real("h", causality=Fmi2Causality.output, start=1, variability=Fmi2Variability.continuous, initial=Fmi2Initial.exact))
        self.register_variable(Real("derh", causality=Fmi2Causality.local, variability=Fmi2Variability.continuous, derivative=1))
        self.register_variable(Real("v", causality=Fmi2Causality.output, start=0, variability=Fmi2Variability.continuous, initial=Fmi2Initial.exact))
        self.register_variable(Real("derv", causality=Fmi2Causality.local, variability=Fmi2Variability.continuous, derivative=3))

        self.register_variable(Real("g", causality=Fmi2Causality.parameter, variability=Fmi2Variability.fixed))
        self.register_variable(Real("e", causality=Fmi2Causality.parameter, variability=Fmi2Variability.tunable))
        self.register_variable(Real("v_min", variability=Fmi2Variability.constant, start=0.1))

    def do_step(self, current_time, step_size):
        print("do_step\n")
        return True
