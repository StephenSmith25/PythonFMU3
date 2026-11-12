"""Conjugate heat transfer demo: the 1D pipe model coupled to a solid wall model.

A heated, thick-walled steel tube: the heater applies a uniform heat flux on the outer
surface of the middle third of the tube, the rest of the outer surface is insulated, and
water flows inside. The solid stands in for your 3D solver: it is an axisymmetric (x, r)
conduction model with the same N axial segments as the pipe, and M radial cells.

Coupling (Robin / "h and T_fluid" exchange), every communication step dt:
    1. solid -> pipe:  T_wall[i]   (inner-surface temperature of segment i)
    2. pipe.do_step(t, dt)
    3. pipe -> solid:  T_fluid[i], h[i]
    4. solid advances dt with q'' = h[i] * (T_surface - T_fluid[i]) on the inner surface

Run:  python cht_demo.py            (uses the Pipe1D class directly)
      python cht_demo.py --segments 50
      python cht_demo.py --fmu Pipe1D.fmu   (uses the built FMU through FMPy)

With a 3D solver, replace SolidWall by your solver: area-average its wetted-wall
temperature over each axial segment for T_wall, and apply each segment's h and T_fluid as
its convective boundary condition.
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from pipe1d import Pipe1D  # noqa: E402


class SolidWall:
    """Axisymmetric conduction in a tube wall (explicit finite volume, sub-stepped)."""

    def __init__(self, length, r_inner, r_outer, n_axial, n_radial=6,
                 k=16.0, rho=7900.0, cp=500.0, T0=293.15):
        self.k, self.rho_cp = k, rho * cp
        self.n, self.m = n_axial, n_radial
        self.dx = length / n_axial
        self.r_faces = np.linspace(r_inner, r_outer, n_radial + 1)
        self.r = 0.5 * (self.r_faces[1:] + self.r_faces[:-1])
        self.dr = self.r_faces[1] - self.r_faces[0]
        self.T = np.full((n_axial, n_radial), T0)
        self.q_outer = np.zeros(n_axial)   # W/m2 into the solid at r_outer
        self.volume = math.pi * (self.r_faces[1:] ** 2 - self.r_faces[:-1] ** 2) * self.dx   # (m,)
        alpha = k / self.rho_cp
        self.dt_max = 0.2 * min(self.dx, self.dr) ** 2 / alpha

    def wall_temperature(self, h, T_fluid):
        """Inner-surface temperature, from a half-cell conduction / convection balance."""
        g = self.k / (0.5 * self.dr)
        return (g * self.T[:, 0] + h * T_fluid) / (g + h)

    def advance(self, dt, h, T_fluid):
        steps = max(1, math.ceil(dt / self.dt_max))
        sub = dt / steps
        A_ax = math.pi * (self.r_faces[1:] ** 2 - self.r_faces[:-1] ** 2)   # axial face areas (m,)
        A_rad = 2.0 * math.pi * self.r_faces * self.dx                        # radial face areas (m+1,)
        for _ in range(steps):
            Q = np.zeros_like(self.T)
            # radial conduction between cells
            flux_r = self.k * A_rad[1:-1] * (self.T[:, 1:] - self.T[:, :-1]) / self.dr
            Q[:, :-1] += flux_r
            Q[:, 1:] -= flux_r
            # axial conduction between segments (insulated ends)
            flux_x = self.k * A_ax * (self.T[1:, :] - self.T[:-1, :]) / self.dx
            Q[:-1, :] += flux_x
            Q[1:, :] -= flux_x
            # inner surface: convection to the fluid (series with the half-cell)
            T_s = self.wall_temperature(h, T_fluid)
            Q[:, 0] -= h * A_rad[0] * (T_s - T_fluid)
            # outer surface: heater
            Q[:, -1] += self.q_outer * A_rad[-1]
            self.T += sub * Q / (self.rho_cp * self.volume)

    def energy(self):
        return float(np.sum(self.rho_cp * self.volume * self.T))


class PythonPipe:
    """Drives the Pipe1D class directly, through the same calls an importer would make."""

    def __init__(self, segments, **parameters):
        self.model = Pipe1D(instance_name="pipe")
        self.model.N = segments          # structural parameter: resizes the arrays
        for name, value in parameters.items():
            setattr(self.model, name, value)
        self.model.enter_initialization_mode()
        self.model.exit_initialization_mode()

    def set(self, name, value):
        setattr(self.model, name, value)

    def get(self, name):
        return np.atleast_1d(np.asarray(getattr(self.model, name), dtype=float))

    def do_step(self, t, dt):
        self.model.do_step(t, dt)


class FmuPipe:
    """Drives the built FMU through FMPy (pip install fmpy)."""

    def __init__(self, fmu_path, segments, **parameters):
        from fmpy import extract, read_model_description
        from fmpy.fmi3 import FMU3Slave

        md = read_model_description(fmu_path)
        self.vr = {v.name: v.valueReference for v in md.modelVariables}
        self.size = {v.name: (segments if v.dimensions else 1) for v in md.modelVariables}
        self.fmu = FMU3Slave(guid=md.guid, unzipDirectory=extract(fmu_path),
                             modelIdentifier=md.coSimulation.modelIdentifier, instanceName="pipe")
        self.fmu.instantiate()
        # The structural parameter N is set in Configuration Mode
        self.fmu.enterConfigurationMode()
        self.fmu.setUInt64([self.vr["N"]], [segments])
        self.fmu.exitConfigurationMode()
        self.fmu.enterInitializationMode()
        for name, value in parameters.items():
            self.set(name, value)
        self.fmu.exitInitializationMode()

    def set(self, name, value):
        values = np.atleast_1d(np.asarray(value, dtype=float))
        self.fmu.setFloat64([self.vr[name]], list(values))

    def get(self, name):
        return np.asarray(self.fmu.getFloat64([self.vr[name]], nValues=self.size[name]), dtype=float)

    def do_step(self, t, dt):
        self.fmu.doStep(currentCommunicationPoint=t, communicationStepSize=dt)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fmu", help="use this built Pipe1D FMU (via FMPy) instead of the Python class")
    parser.add_argument("--end", type=float, default=1200.0, help="end time [s]")
    parser.add_argument("--dt", type=float, default=1.0, help="communication step [s]")
    parser.add_argument("--segments", type=int, default=20, help="number of axial segments N")
    parser.add_argument("--plot", help="save a plot to this file (needs matplotlib)")
    args = parser.parse_args()

    length, d_inner, d_outer = 2.0, 0.02, 0.03
    m_dot, T_in, heat_flux = 0.1, 293.15, 50e3      # kg/s, K, W/m2 on the heated outer surface

    n = args.segments
    params = dict(length=length, diameter=d_inner, T_initial=T_in)
    pipe = FmuPipe(args.fmu, n, **params) if args.fmu else PythonPipe(n, **params)
    pipe.set("m_dot", m_dot)
    pipe.set("T_in", T_in)

    solid = SolidWall(length, d_inner / 2, d_outer / 2, n, T0=T_in)
    third = n // 3
    solid.q_outer[third:2 * third] = heat_flux
    heater_power = heat_flux * math.pi * d_outer * (length / n) * third

    h, T_fluid = pipe.get("h"), pipe.get("T_fluid")
    t = 0.0
    print(f"{'t [s]':>7} {'T_out [K]':>10} {'max T_wall [K]':>15} {'Q to fluid [W]':>15}")
    while t < args.end - 1e-9:
        pipe.set("T_wall", solid.wall_temperature(h, T_fluid))
        pipe.do_step(t, args.dt)
        h, T_fluid = pipe.get("h"), pipe.get("T_fluid")
        solid.advance(args.dt, h, T_fluid)
        t += args.dt
        if abs(t % 120.0) < 1e-6 or t >= args.end - 1e-9:
            T_wall = solid.wall_temperature(h, T_fluid)
            print(f"{t:7.0f} {pipe.get('T_out')[0]:10.2f} {T_wall.max():15.2f} {pipe.get('Q_total')[0]:15.1f}")

    absorbed = m_dot * 4179.0 * (pipe.get("T_out")[0] - T_in)
    print(f"\nheater power {heater_power:.1f} W, enthalpy rise of the water {absorbed:.1f} W "
          f"({100 * absorbed / heater_power:.1f}% at t = {t:.0f} s)")
    print(f"Re = {pipe.get('Re')[0]:.0f}, Nu = {pipe.get('Nu')[0]:.1f}, h = {h[0]:.0f} W/(m2.K), "
          f"dp = {pipe.get('dp')[0]:.1f} Pa")

    if args.plot:
        import matplotlib.pyplot as plt
        x = pipe.get("x")
        plt.plot(x, solid.wall_temperature(h, T_fluid) - 273.15, label="wall (inner surface)")
        plt.plot(x, T_fluid - 273.15, label="fluid (bulk)")
        plt.axvspan(x[third] - length / n / 2, x[2 * third - 1] + length / n / 2,
                    alpha=0.15, label="heated section")
        plt.xlabel("x [m]")
        plt.ylabel("temperature [°C]")
        plt.legend()
        plt.title(f"Pipe CHT at t = {t:.0f} s")
        plt.savefig(args.plot, dpi=150, bbox_inches="tight")
        print(f"plot saved to {args.plot}")


if __name__ == "__main__":
    main()
