from pythonfmu3 import Fmi3Causality, ModelExchange, Fmi3Variability, Fmi3SlaveBase, Fmi3Status, Float64, Fmi3Initial, Unit, Float64Type, Fmi3StepResult

from typing import List

class Robertson(Fmi3SlaveBase, ModelExchange):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "Stephen Smith"
        self.description = "Robertson test problem"

        self.time = 0.0
        self.y1 = 1
        self.y2 = 0
        self.y3 = 0
        self.dery1 = -0.04
        self.dery2 = 0.04
        self.dery3 = 0.0

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("y1", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact))
        self.register_variable(Float64("y2", causality=Fmi3Causality.output, start=0, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact))
        self.register_variable(Float64("y3", causality=Fmi3Causality.output, start=0, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact))
        self.register_variable(Float64("dery1", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=1))
        self.register_variable(Float64("dery2", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=2))
        self.register_variable(Float64("dery3", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=3))


    def get_continuous_state_derivatives(self) -> List[float]:
        self.dery1 = -0.04 * self.y1 + 1e4 * self.y2 * self.y3
        self.dery2 = 0.04 * self.y1 - 1e4 * self.y2 * self.y3 - 3e7 * self.y2**2
        self.dery3 = 3e7 * self.y2**2
        return [self.dery1, self.dery2, self.dery3]