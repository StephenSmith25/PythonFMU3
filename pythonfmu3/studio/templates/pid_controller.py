"""PID controller with output limits and anti-windup (Co-Simulation)."""
from pythonfmu3 import Fmi3Causality, Fmi3Slave, Fmi3Variability, Float64


class PIDController(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.author = "PythonFMU3 Studio template"
        self.description = "PID controller with output limits and anti-windup"

        self.time = 0.0
        self.setpoint = 1.0
        self.measurement = 0.0
        self.output = 0.0
        self.Kp = 2.0
        self.Ki = 1.0
        self.Kd = 0.1
        self.u_min = -10.0
        self.u_max = 10.0
        self._integral = 0.0
        self._previous_error = None

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("setpoint", causality=Fmi3Causality.input, start=1.0))
        self.register_variable(Float64("measurement", causality=Fmi3Causality.input, start=0.0))
        self.register_variable(Float64("output", causality=Fmi3Causality.output))
        for name in ("Kp", "Ki", "Kd", "u_min", "u_max"):
            self.register_variable(Float64(name, causality=Fmi3Causality.parameter,
                                           variability=Fmi3Variability.tunable, start=getattr(self, name)))

    def do_step(self, current_time, step_size):
        error = self.setpoint - self.measurement
        derivative = 0.0 if self._previous_error is None else (error - self._previous_error) / step_size
        candidate = self._integral + error * step_size
        u = self.Kp * error + self.Ki * candidate + self.Kd * derivative
        if self.u_min < u < self.u_max:          # anti-windup: integrate only when not saturated
            self._integral = candidate
        self.output = min(max(u, self.u_min), self.u_max)
        self._previous_error = error
        self.time = current_time + step_size
        return True
