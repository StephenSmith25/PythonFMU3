from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3SlaveBase, ModelExchange, Fmi3Status, Float64, Fmi3Initial, Unit, Fmi3UpdateDiscreteStatesResult

from typing import List

import sys

EVENT_EPS = 1e-12

class BouncingBall(Fmi3SlaveBase, ModelExchange):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "..."
        self.description = "Bouncing Ball"

        self.time = 0.0
        self.h = 1.0
        self.v = 0.0
        self.derh = 0.0
        self.derv = 0.0
        self.g = -9.81
        self.e = 0.7
        self.v_min = 0.1

        # define units
        unit1 = Unit(name="m", m=1)
        unit2 = Unit(name="m/s", m=1, s=-1)
        unit3 = Unit(name="m/s2", m=1, s=-2)
        self.register_units([unit1, unit2, unit3])


        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))

        self.register_variable(Float64("ball.h", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact, unit=unit1.name),
                                nested=False, has_event_indicator=True)
        self.register_variable(Float64("ball.derh", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=1, unit=unit2.name),
                                nested=False)
        self.register_variable(Float64("ball.v", causality=Fmi3Causality.output, start=0, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact, unit=unit2.name),
                               nested=False)
        self.register_variable(Float64("ball.derv", causality=Fmi3Causality.local, variability=Fmi3Variability.continuous, derivative=3, unit=unit3.name),
                                nested=False)

        self.register_variable(Float64("g", causality=Fmi3Causality.parameter, variability=Fmi3Variability.fixed, unit=unit3.name))
        self.register_variable(Float64("e", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable))
        self.register_variable(Float64("v_min", variability=Fmi3Variability.constant, start=0.1))
        


    def get_continuous_state_derivatives(self) -> List[float]:
        self.derh = self.v
        self.derv = self.g
        return [self.derh, self.derv]
        
    def get_event_indicators(self) -> List[float]:
        z = [self.h]
        if self.h > -EVENT_EPS and self.h <=0 and self.v > 0:
            z[0] = -EVENT_EPS

        return z
    
    def update_discrete_states(self):
        fdsr = Fmi3UpdateDiscreteStatesResult()

        if self.h <= 0 and self.v < 0:
            self.h = sys.float_info.min
            self.v = -self.v * self.e
            
            if self.v < self.v_min:
                self.v = 0.0;
                self.g = 0.0;
            
            fdsr.valuesOfContinuousStatesChanged = True

        return fdsr
