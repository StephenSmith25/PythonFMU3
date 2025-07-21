from pythonfmu3 import Fmi3Causality, ModelExchange, Fmi3Variability, Fmi3SlaveBase, Fmi3Status, Float64, Fmi3Initial, Unit, Float64Type, Fmi3StepResult

from typing import List

class VanDerPol(Fmi3SlaveBase, ModelExchange):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "Stephen Smith"
        self.description = "Van Der Pol oscillator problem for model exchange FMUs"

        self.time = 0.0
        self.mu = 1.0
        self.x0 = 2
        self.x1 = 0
        self.derx0 = 0.0
        self.derx1 = 0.0

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("x0", causality=Fmi3Causality.output, start=2, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact))
        self.register_variable(Float64("x1", causality=Fmi3Causality.output, start=0, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact))
        self.register_variable(Float64("derx0", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=1))
        self.register_variable(Float64("derx1", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=2))
        self.register_variable(Float64("mu", causality=Fmi3Causality.parameter, variability=Fmi3Variability.fixed))


    def get_continuous_state_derivatives(self) -> List[float]:
        self.derx0 = self.x1
        self.derx1 = self.mu * ((1 - self.x0**2) * self.x1) - self.x0
        return [self.derx0, self.derx1]
       