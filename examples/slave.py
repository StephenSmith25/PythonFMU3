from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Float64, Fmi3Initial, Dimension
import numpy as np
import dataclasses
import xmlrpc.client
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclasses.dataclass
class FaceContainer:
    Pressure: np.array
    Shear: np.array
    vertices: np.array
    normals: np.array
    nvertices: int

class TransolverSlave(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "..."
        self.description = "Transolver Example Slave Using RPC"

        self.time = 0.0
        self.num_points = 121
        self.vertices_dim = self.num_points * 3
        self.normals_dim = self.num_points * 3

        self.client = False

        self.face1 = FaceContainer(Pressure=np.zeros(self.num_points),
                                    Shear=np.zeros(shape=(self.num_points, 3)),
                                    vertices=np.zeros(shape=(self.num_points, 3)),
                                    normals=np.zeros(shape=(self.num_points, 3)),
                                    nvertices=self.num_points)

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability="continuous"))

        self.register_variable(Float64("face1.Pressure",
                                   causality=Fmi3Causality.output,
                                   getter=lambda: self.pressure_getter(),
                                   variability="continuous",
                                   initial=Fmi3Initial.calculated,
                                   dimensions=[Dimension(start=f"{self.num_points}")]),
                                   nested=True)

        self.register_variable(Float64("face1.Shear",
                                   causality=Fmi3Causality.output,
                                   getter=lambda: self.shear_getter(),
                                   variability="continuous",
                                   initial=Fmi3Initial.calculated,
                                   dimensions=[Dimension(start=f"{self.num_points}"), Dimension(start=f"{3}")]),
                                   nested=True)

        self.register_variable(Float64("face1.vertices",
                                   causality=Fmi3Causality.input,
                                   setter=lambda v: self.vertices_setter(v),
                                   variability="continuous",
                                   initial=Fmi3Initial.exact,
                                   start=0.0,
                                   dimensions=[Dimension(start=f"{self.vertices_dim}"), Dimension(start=f"{3}")]), nested=True)

        self.register_variable(Float64("face1.normals",
                                   causality=Fmi3Causality.input,
                                   setter=lambda v: self.normals_setter(v),
                                   variability="continuous",
                                   start=0.0,
                                   initial=Fmi3Initial.exact,
                                   dimensions=[Dimension(start=f"{self.normals_dim}"), Dimension(start=f"{3}")]), nested=True)


    def enter_initialization_mode(self):
        try:
            logging.info("Entering initialization mode...")
            self.client = xmlrpc.client.ServerProxy("http://localhost:8001/", allow_none=True)
            if self.client.initialize():
                logging.info("Initialization successful.")
            else:
                logging.error("Initialization failed on server.")
        except Exception as e:
            logging.error(f"Error during initialization: {e}")

    def pressure_getter(self):
        if self.client:
            try:
                pressure = self.client.getPressure()
                if pressure:
                    return np.array(pressure).flatten()
                else:
                    logging.warning("Received empty pressure from server, returning zeros.")
                    return np.zeros(self.num_points)

            except Exception as e:
                logging.error(f"Error getting pressure from server: {e}")
                return np.zeros(self.num_points)
        else:
            return self.face1.Pressure
    
    def shear_getter(self):
        if self.client:
            try:
                shear = self.client.getShear()
                if shear:
                    return np.array(shear).flatten()
                else:
                    logging.warning("Received empty shear from server, returning zeros.")
                    return np.zeros(self.num_points, 3)

            except Exception as e:
                logging.error(f"Error getting shear from server: {e}")
                return np.zeros(self.num_points)
        else:
            return self.face1.Shear

    def vertices_setter(self, v):
        try:
            if self.client:
                self.client.setVertices(v)
            else:
                self.face1.vertices = np.reshape(v, newshape=(self.face1.nvertices, 3))
        except Exception as e:
            logging.error(f"Error setting vertices: {e}")

    def normals_setter(self, v):
        try:
            if self.client:
                self.client.setNormals(v)
            else:
                self.face1.normals = np.reshape(v, newshape=(self.face1.nvertices, 3))
        except Exception as e:
            logging.error(f"Error setting normals: {e}")

    def do_step(self, current_time, step_size):
        return True
