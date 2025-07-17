from pythonfmu3 import Fmi3Causality, Fmi3Interface, ModelExchange, Fmi3Variability, Fmi3SlaveBase, Fmi3Status, Float64, Fmi3Initial, Unit, Float64Type, Fmi3StepResult

from typing import List

class Dahlquist(Fmi3SlaveBase, ModelExchange):

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


    def get_continuous_states(self) -> List[float]:
        return [self.x]
    
    def set_continuous_states(self, values: List[float]):
        self.x = values[0]
    
    def get_continuous_state_derivatives(self) -> List[float]:
        vals = [-self.k*self.x]
        return vals
       
    def set_time(self, time: float):
        self.time = time
        
    def get_number_of_continuous_states(self) -> int:
        return 1