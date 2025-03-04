from dataclasses import dataclass
from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Float64, Fmi3Initial, Unit, Float64Type, Dimension
import numpy as np


def create_face(num_points, face='x=1'):
    """
    Create points on the face of a cuboid with dimensions [2, 2, 2], centered at [0, 0, 0].
    
    Parameters:
    - num_points: Number of points along one dimension of the face.
    - face: The face of the cuboid to generate points on. Options are 'x=1', 'x=-1', 'y=1', 'y=-1', 'z=1', 'z=-1'.
    
    Returns:
    - vertices: A NumPy array of shape (num_points*num_points, 3) containing the points on the specified face.
    """
    linspace = np.linspace(-1, 1, num_points)
    y, z = np.meshgrid(linspace, linspace)
    y = y.flatten()
    z = z.flatten()
    
    if face == 'x=1':
        x = np.ones_like(y)
    elif face == 'x=-1':
        x = -np.ones_like(y)
    elif face == 'y=1':
        x = np.meshgrid(linspace, linspace)[0].flatten()
        y = np.ones_like(x)
    elif face == 'y=-1':
        x = np.meshgrid(linspace, linspace)[0].flatten()
        y = -np.ones_like(x)
    elif face == 'z=1':
        x, y = np.meshgrid(linspace, linspace)
        x = x.flatten()
        y = y.flatten()
        z = np.ones_like(x)
    elif face == 'z=-1':
        x, y = np.meshgrid(linspace, linspace)
        x = x.flatten()
        y = y.flatten()
        z = -np.ones_like(x)

    vertices = np.vstack((x, y, z)).T
    return vertices
  


@dataclass
class FaceContainer:
  """ Class for storing face data """
  Pressure : np.array
  vertices : np.array

class CuboidGeom(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "..."
        self.description = "Cuboid with Geometry"

        num_points = 10
        self.time = 0.0

        self.face1 = FaceContainer(Pressure=np.zeros(num_points*num_points), vertices=create_face(num_points, face='x=1'))
        self.face2 = FaceContainer(Pressure=np.zeros(num_points*num_points), vertices=create_face(num_points, face='x=-1'))
        self.face3 = FaceContainer(Pressure=np.zeros(num_points*num_points), vertices=create_face(num_points, face='y=1'))
        self.face4 = FaceContainer(Pressure=np.zeros(num_points*num_points), vertices=create_face(num_points, face='y=-1'))
        self.face5 = FaceContainer(Pressure=np.zeros(num_points*num_points), vertices=create_face(num_points, face='z=1'))
        self.face6 = FaceContainer(Pressure=np.zeros(num_points*num_points), vertices=create_face(num_points, face='z=-1'))

        
        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))

        # face 1
        self.register_variable(Float64("face1.Pressure", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                dimensions=[Dimension(start=f"{num_points*num_points}")]), nested=True)
        self.register_variable(Float64("face1.vertices", causality=Fmi3Causality.parameter, variability = Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                        dimensions=[Dimension(start=f"{num_points*num_points}"), Dimension(start=f"{3}")]), nested=True)
        # face 2
        self.register_variable(Float64("face2.Pressure", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                dimensions=[Dimension(start=f"{num_points*num_points}")]), nested=True)
        self.register_variable(Float64("face2.vertices", causality=Fmi3Causality.parameter, variability = Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                        dimensions=[Dimension(start=f"{num_points*num_points}"), Dimension(start=f"{3}")]), nested=True)
        
        # face 3
        self.register_variable(Float64("face3.Pressure", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                dimensions=[Dimension(start=f"{num_points*num_points}")]), nested=True)
        self.register_variable(Float64("face3.vertices", causality=Fmi3Causality.parameter, variability = Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                        dimensions=[Dimension(start=f"{num_points*num_points}"), Dimension(start=f"{3}")]), nested=True)
        # face 4
        self.register_variable(Float64("face4.Pressure", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                dimensions=[Dimension(start=f"{num_points*num_points}")]), nested=True)
        self.register_variable(Float64("face4.vertices", causality=Fmi3Causality.parameter, variability = Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                        dimensions=[Dimension(start=f"{num_points*num_points}"), Dimension(start=f"{3}")]), nested=True)
        
        # face 5
        self.register_variable(Float64("face5.Pressure", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                dimensions=[Dimension(start=f"{num_points*num_points}")]), nested=True)
        self.register_variable(Float64("face5.vertices", causality=Fmi3Causality.parameter, variability = Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                        dimensions=[Dimension(start=f"{num_points*num_points}"), Dimension(start=f"{3}")]), nested=True)
        
        # face 6
        self.register_variable(Float64("face6.Pressure", causality=Fmi3Causality.output, start=1, variability=Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                dimensions=[Dimension(start=f"{num_points*num_points}")]), nested=True)
        self.register_variable(Float64("face6.vertices", causality=Fmi3Causality.parameter, variability = Fmi3Variability.continuous, initial=Fmi3Initial.exact,
                                        dimensions=[Dimension(start=f"{num_points*num_points}"), Dimension(start=f"{3}")]), nested=True)

    def do_step(self, current_time, step_size):
        self.face1.Pressure = np.random.rand(self.face1.Pressure.shape[0])
        self.face2.Pressure = np.random.rand(self.face2.Pressure.shape[0])
        self.face3.Pressure = np.random.rand(self.face3.Pressure.shape[0])
        self.face4.Pressure = np.random.rand(self.face4.Pressure.shape[0])
        self.face5.Pressure = np.random.rand(self.face5.Pressure.shape[0])
        self.face6.Pressure = np.random.rand(self.face6.Pressure.shape[0])
        return True
