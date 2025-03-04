from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Float64, String


class Resistor(Fmi3Slave):


    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "John Doe"
        self.description = "A simple description"

        self.time = 0.0

        self.positive_pin_v = 20.
        self.positive_pin_i = 0.001
        self.negative_pin_v = 10.
        self.negative_pin_i = 0.001
        self.delta_v = 10.
        self.i = 0.001
        self.R = 10000.
        self.stringVariable = "mine"

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("R", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable))

        self.register_variable(Float64("positive_pin_v", causality=Fmi3Causality.input))
        self.register_variable(Float64("positive_pin_i", causality=Fmi3Causality.output))
        self.register_variable(Float64("negative_pin_v", causality=Fmi3Causality.input))
        self.register_variable(Float64("negative_pin_i", causality=Fmi3Causality.output))

        self.register_variable(Float64("delta_v", causality=Fmi3Causality.local))
        self.register_variable(Float64("i", causality=Fmi3Causality.local))

        self.register_variable(String("stringVariable", causality=Fmi3Causality.parameter))
    
    def enter_initialization_mode(self):
        raise RuntimeError("This is an error message")

    def do_step(self, current_time, step_size):
        self.delta_v = self.positive_pin_v - self.negative_pin_v
        self.i = i = self.delta_v / self.R
        self.positive_pin_i = i
        self.negative_pin_i = -i
        return True
