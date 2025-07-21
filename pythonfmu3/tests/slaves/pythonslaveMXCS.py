from pythonfmu3 import Fmi3Causality, CoSimulation, ModelExchange, Fmi3Variability, Fmi3SlaveBase, Fmi3Status, Float64, Fmi3Initial, Unit, Float64Type, Fmi3StepResult

from typing import List

class Dahlquist(Fmi3SlaveBase, ModelExchange, CoSimulation):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "Stephen Smith"
        self.description = "Dahlquist's test problem for model exchange FMUs"

        self.time = 0.0
        self.k = 1.0
        self.x = 1.0
        self.derx = 0.0

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("x", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact))
        self.register_variable(Float64("derx", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=1))
        self.register_variable(Float64("k", causality=Fmi3Causality.parameter, variability=Fmi3Variability.fixed))


    def get_continuous_state_derivatives(self) -> List[float]:
        self.derx = -self.k * self.x
        return [self.derx]
       
    def do_step(self, current_time: float, step_size: float) -> Fmi3StepResult:
        self.time = current_time + step_size
        self.derx = -self.k * self.x
        self.x += self.derx * step_size
        return True