from dataclasses import dataclass
from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Float64, Fmi3Initial, Unit, Float64Type, Dimension
import numpy as np


@dataclass
class FaceContainer:
  """ Class for storing face data """
  Pressure : np.array
  vertices : np.array
  nvertices : int

class InputGeom(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "..."
        self.description = "Input Geometry"
        
        self.time = 0.0
        num_points = 144
        self.face1 = FaceContainer(Pressure=np.zeros(num_points), vertices=np.zeros(shape=(num_points, 3)), nvertices=num_points)

        
        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))

        # face 1
        self.register_variable(Float64("face1.Pressure", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                dimensions=[Dimension(start=f"{num_points}")]), nested=True)
        self.register_variable(Float64("face1.vertices", causality=Fmi3Causality.input, variability = Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                        dimensions=[Dimension(start=f"{num_points}"), Dimension(start=f"{3}")]), nested=True)

    def do_step(self, current_time, step_size):
        self.face1.Pressure = np.random.rand(self.face1.Pressure.shape[0])
        return True
