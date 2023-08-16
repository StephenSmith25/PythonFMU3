from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Float64, Int64, Enumeration, Fmi3Initial


class Enum(Fmi3Slave):

    author = "..."
    description = "Bouncing Ball"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # self.time = 0.0
        self.x = 0.0
        self.int64 = 2
        
        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("x", causality=Fmi3Causality.output, initial=Fmi3Initial.calculated))
        self.register_variable(Int64("int64", causality=Fmi3Causality.input, start=2))

    def do_step(self, current_time, step_size):
        self.x += 1.0*self.int64
        return True
