from pythonfmu import Fmi2Causality, Fmi2Variability, Fmi2Slave, Real


class Counter(Fmi2Slave):

    author = "John Doe"
    description = "A simple description"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.counter = 0
        
        self.register_variable(Real("time", causality=Fmi2Causality.independent, variability=Fmi2Variability.continuous))

        self.register_variable(Real("counter", causality=Fmi2Causality.output))

    def do_step(self, current_time, step_size):
        print("do_step\n")
        self.counter += 1
        return True
