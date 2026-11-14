"""A heated room with an on/off thermostat and hysteresis (Co-Simulation)."""
from pythonfmu3 import Boolean, Fmi3Causality, Fmi3Slave, Fmi3Variability, Float64, Int32, Unit


class Thermostat(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.author = "PythonFMU3 Studio template"
        self.description = "Room temperature with an on/off heater and hysteresis"

        self.time = 0.0
        self.T_room = 15.0          # degC
        self.T_outside = 5.0        # degC, input
        self.T_set = 20.0           # degC
        self.hysteresis = 1.0       # K
        self.heater_power = 2000.0  # W
        self.UA = 50.0              # W/K, losses to outside
        self.C = 5e5                # J/K, room heat capacity
        self.heater_on = False
        self.switches = 0

        self.register_units([Unit(name="degC", K=1, offset=273.15), Unit(name="W", kg=1, m=2, s=-3),
                             Unit(name="W/K", kg=1, m=2, s=-3, K=-1), Unit(name="J/K", kg=1, m=2, s=-2, K=-1)])
        tunable = dict(causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable)
        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("T_outside", causality=Fmi3Causality.input, start=5.0, unit="degC"))
        self.register_variable(Float64("T_room", causality=Fmi3Causality.output, unit="degC"))
        self.register_variable(Boolean("heater_on", causality=Fmi3Causality.output, variability=Fmi3Variability.discrete))
        self.register_variable(Int32("switches", causality=Fmi3Causality.output, variability=Fmi3Variability.discrete))
        self.register_variable(Float64("T_set", start=20.0, unit="degC", **tunable))
        self.register_variable(Float64("hysteresis", start=1.0, **tunable))
        self.register_variable(Float64("heater_power", start=2000.0, unit="W", **tunable))
        self.register_variable(Float64("UA", start=50.0, unit="W/K", **tunable))
        self.register_variable(Float64("C", start=5e5, unit="J/K", **tunable))

    def do_step(self, current_time, step_size):
        if self.heater_on and self.T_room > self.T_set + self.hysteresis / 2:
            self.heater_on, self.switches = False, self.switches + 1
        elif not self.heater_on and self.T_room < self.T_set - self.hysteresis / 2:
            self.heater_on, self.switches = True, self.switches + 1
        q = (self.heater_power if self.heater_on else 0.0) - self.UA * (self.T_room - self.T_outside)
        self.T_room += q * step_size / self.C
        self.time = current_time + step_size
        return True
