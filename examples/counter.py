from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Float64, Int32


class Counter(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "John Doe"
        self.description = "A simple description"

        self.time = 0.0
        self.counter = 0

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))

        self.register_variable(Int32("counter", causality=Fmi3Causality.output))

    def do_step(self, current_time, step_size):
        self.counter += 1
        return True
