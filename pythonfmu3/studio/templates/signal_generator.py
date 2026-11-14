"""Test-bench signal source: sine, square or ramp, selected by an integer mode."""
import math

from pythonfmu3 import Fmi3Causality, Fmi3Slave, Fmi3Variability, Float64, Int32


class SignalGenerator(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.author = "PythonFMU3 Studio template"
        self.description = "Sine (mode 0), square (1) or ramp (2) signal"

        self.time = 0.0
        self.mode = 0
        self.amplitude = 1.0
        self.frequency = 0.5
        self.offset = 0.0
        self.y = 0.0

        tunable = dict(causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable)
        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Int32("mode", start=0, **tunable))
        self.register_variable(Float64("amplitude", start=1.0, **tunable))
        self.register_variable(Float64("frequency", start=0.5, **tunable))
        self.register_variable(Float64("offset", start=0.0, **tunable))
        self.register_variable(Float64("y", causality=Fmi3Causality.output))

    def do_step(self, current_time, step_size):
        t = current_time + step_size
        phase = (t * self.frequency) % 1.0
        if self.mode == 1:
            wave = 1.0 if phase < 0.5 else -1.0
        elif self.mode == 2:
            wave = 2.0 * phase - 1.0
        else:
            wave = math.sin(2 * math.pi * phase)
        self.y = self.offset + self.amplitude * wave
        self.time = t
        return True
