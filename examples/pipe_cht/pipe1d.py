"""1D pipe flow with wall heat transfer, for conjugate heat transfer (CHT) co-simulation.

The fluid is resolved along the pipe axis only (N segments). The pipe wall belongs to a
separate solid solver (e.g. a 3D conduction model) that exchanges, per axial segment:

    solid -> FMU:  T_wall[i]   area-averaged wall temperature of segment i   [K]
    FMU -> solid:  T_fluid[i]  bulk fluid temperature of segment i           [K]
                   h[i]        heat transfer coefficient of segment i        [W/(m2.K)]

so the solid applies a convective (Robin) condition  q'' = h[i] * (T_solid - T_fluid[i])
on the wetted surface of segment i. This Robin coupling is the usual stable choice for CHT;
q_wall[i] (heat flux into the fluid) is also provided for a Neumann-type coupling.

Model, per segment (finite volume, first-order upwind, implicit Euler):

    rho*cp*A*dx * dT_i/dt = m_dot*cp*(T_up - T_i) + h_i*P*dx*(T_wall_i - T_i)

The implicit upwind system is (bi)diagonal, so each step is one O(N) sweep and is stable for
any communication step size. Reverse flow (m_dot < 0) is supported: T_in then enters at x=L.

Heat transfer: fully developed Nusselt number, Nu = 3.66 (laminar, Re < 2300) and
Gnielinski (Re > 4000), blended linearly in between. Friction: f = 64/Re (laminar) and
Petukhov (turbulent). Constant fluid properties (defaults: water at about 40 C).

Build:  pythonfmu3 build -f pipe1d.py
"""
import math

import numpy as np

from pythonfmu3 import (
    Dimension,
    Fmi3Causality,
    Fmi3Initial,
    Fmi3Slave,
    Fmi3Variability,
    Float64,
    Unit,
)

# Number of axial segments. Array sizes are fixed when the FMU is built: change this
# value and rebuild for a different resolution.
N_SEGMENTS = 20

RE_LAMINAR = 2300.0
RE_TURBULENT = 4000.0


def friction_factor(re: float) -> float:
    """Darcy friction factor of a smooth pipe."""
    if re <= 0.0:
        return 0.0
    laminar = 64.0 / max(re, 1e-12)
    if re <= RE_LAMINAR:
        return laminar
    turbulent = (0.790 * math.log(max(re, RE_TURBULENT)) - 1.64) ** -2  # Petukhov
    if re >= RE_TURBULENT:
        return turbulent
    w = (re - RE_LAMINAR) / (RE_TURBULENT - RE_LAMINAR)
    return (1.0 - w) * laminar + w * turbulent


def nusselt(re: float, pr: float) -> float:
    """Fully developed Nusselt number: 3.66 laminar, Gnielinski turbulent, blended in between."""
    laminar = 3.66
    if re <= RE_LAMINAR:
        return laminar
    re_t = max(re, RE_TURBULENT)
    f = (0.790 * math.log(re_t) - 1.64) ** -2
    turbulent = (f / 8.0) * (re_t - 1000.0) * pr / (1.0 + 12.7 * math.sqrt(f / 8.0) * (pr ** (2.0 / 3.0) - 1.0))
    if re >= RE_TURBULENT:
        return turbulent
    w = (re - RE_LAMINAR) / (RE_TURBULENT - RE_LAMINAR)
    return (1.0 - w) * laminar + w * turbulent


class Pipe1D(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "PythonFMU3 examples"
        self.description = "1D pipe flow with wall heat transfer for CHT coupling with a solid solver"

        n = N_SEGMENTS
        self.time = 0.0

        # Parameters
        self.length = 2.0          # m
        self.diameter = 0.02       # m
        self.rho = 992.2           # kg/m3
        self.cp = 4179.0           # J/(kg.K)
        self.k_fluid = 0.631       # W/(m.K)
        self.mu = 6.53e-4          # Pa.s
        self.T_initial = 293.15    # K, initial fluid temperature

        # Inputs
        self.m_dot = 0.05                       # kg/s (positive: from x=0 to x=L)
        self.T_in = 293.15                      # K, temperature of the entering fluid
        self.T_wall = np.full(n, 293.15)        # K, wall temperature per segment

        # Outputs
        self.T_fluid = np.full(n, self.T_initial)   # K, bulk temperature per segment
        self.h = np.zeros(n)                        # W/(m2.K)
        self.q_wall = np.zeros(n)                   # W/m2, wall -> fluid
        self.Q_wall = np.zeros(n)                   # W per segment, wall -> fluid
        self.x = (np.arange(n) + 0.5) * self.length / n   # m, segment centres
        self.T_out = self.T_initial                 # K
        self.Q_total = 0.0                          # W, wall -> fluid over the whole pipe
        self.Re = 0.0
        self.Nu = 0.0
        self.dp = 0.0                               # Pa, frictional pressure drop

        self.register_units([
            Unit(name="K", K=1),
            Unit(name="m", m=1),
            Unit(name="kg/s", kg=1, s=-1),
            Unit(name="kg/m3", kg=1, m=-3),
            Unit(name="J/(kg.K)", m=2, s=-2, K=-1),
            Unit(name="W/(m.K)", kg=1, m=1, s=-3, K=-1),
            Unit(name="W/(m2.K)", kg=1, s=-3, K=-1),
            Unit(name="W/m2", kg=1, s=-3),
            Unit(name="W", kg=1, m=2, s=-3),
            Unit(name="Pa", kg=1, m=-1, s=-2),
            Unit(name="Pa.s", kg=1, m=-1, s=-1),
        ])

        segments = [Dimension(start=str(n))]
        parameter = dict(causality=Fmi3Causality.parameter, variability=Fmi3Variability.fixed)
        output = dict(causality=Fmi3Causality.output, variability=Fmi3Variability.continuous,
                      initial=Fmi3Initial.calculated)

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))

        self.register_variable(Float64("length", start=self.length, unit="m", **parameter))
        self.register_variable(Float64("diameter", start=self.diameter, unit="m", **parameter))
        self.register_variable(Float64("rho", start=self.rho, unit="kg/m3", **parameter))
        self.register_variable(Float64("cp", start=self.cp, unit="J/(kg.K)", **parameter))
        self.register_variable(Float64("k_fluid", start=self.k_fluid, unit="W/(m.K)", **parameter))
        self.register_variable(Float64("mu", start=self.mu, unit="Pa.s", **parameter))
        self.register_variable(Float64("T_initial", start=self.T_initial, unit="K", **parameter))

        self.register_variable(Float64("m_dot", causality=Fmi3Causality.input, variability=Fmi3Variability.continuous,
                                       start=self.m_dot, unit="kg/s"))
        self.register_variable(Float64("T_in", causality=Fmi3Causality.input, variability=Fmi3Variability.continuous,
                                       start=self.T_in, unit="K"))
        self.register_variable(Float64("T_wall", causality=Fmi3Causality.input, variability=Fmi3Variability.continuous,
                                       unit="K", dimensions=segments))

        self.register_variable(Float64("T_fluid", unit="K", dimensions=segments, **output))
        self.register_variable(Float64("h", unit="W/(m2.K)", dimensions=segments, **output))
        self.register_variable(Float64("q_wall", unit="W/m2", dimensions=segments, **output))
        self.register_variable(Float64("Q_wall", unit="W", dimensions=segments, **output))
        self.register_variable(Float64("x", causality=Fmi3Causality.calculatedParameter, variability=Fmi3Variability.fixed,
                                       initial=Fmi3Initial.calculated, unit="m", dimensions=segments))
        self.register_variable(Float64("T_out", unit="K", **output))
        self.register_variable(Float64("Q_total", unit="W", **output))
        self.register_variable(Float64("Re", **output))
        self.register_variable(Float64("Nu", **output))
        self.register_variable(Float64("dp", unit="Pa", **output))

    # --- FMI callbacks -----------------------------------------------------------------

    def exit_initialization_mode(self):
        n = N_SEGMENTS
        self.T_fluid = np.full(n, self.T_initial)
        self.x = (np.arange(n) + 0.5) * self.length / n
        self._update_heat_transfer()
        self._update_outputs()

    def do_step(self, current_time, step_size):
        self._update_heat_transfer()
        self.T_fluid = self._advance(self.T_fluid, step_size)
        self._update_outputs()
        self.time = current_time + step_size
        return True

    # --- model -------------------------------------------------------------------------

    @property
    def _area(self):
        return math.pi * self.diameter ** 2 / 4.0

    @property
    def _perimeter(self):
        return math.pi * self.diameter

    def _update_heat_transfer(self):
        self.Re = abs(self.m_dot) * self.diameter / (self._area * self.mu)
        pr = self.mu * self.cp / self.k_fluid
        self.Nu = nusselt(self.Re, pr)
        self.h = np.full(N_SEGMENTS, self.Nu * self.k_fluid / self.diameter)
        velocity = abs(self.m_dot) / (self.rho * self._area)
        self.dp = friction_factor(self.Re) * self.length / self.diameter * 0.5 * self.rho * velocity ** 2

    def _advance(self, T_old, dt):
        """One implicit-Euler step of the upwind finite-volume energy equation."""
        n = N_SEGMENTS
        dx = self.length / n
        T_wall = np.asarray(self.T_wall, dtype=float).reshape(n)
        storage = self.rho * self.cp * self._area * dx / dt     # W/K
        convection = abs(self.m_dot) * self.cp                  # W/K
        wall = self.h * self._perimeter * dx                    # W/K per segment

        order = range(n) if self.m_dot >= 0.0 else range(n - 1, -1, -1)
        T_new = np.empty(n)
        T_up = self.T_in
        for i in order:
            T_new[i] = (storage * T_old[i] + convection * T_up + wall[i] * T_wall[i]) / (storage + convection + wall[i])
            T_up = T_new[i]
        return T_new

    def _update_outputs(self):
        T_wall = np.asarray(self.T_wall, dtype=float).reshape(N_SEGMENTS)
        self.q_wall = self.h * (T_wall - self.T_fluid)
        self.Q_wall = self.q_wall * self._perimeter * self.length / N_SEGMENTS
        self.Q_total = float(np.sum(self.Q_wall))
        self.T_out = float(self.T_fluid[-1] if self.m_dot >= 0.0 else self.T_fluid[0])
