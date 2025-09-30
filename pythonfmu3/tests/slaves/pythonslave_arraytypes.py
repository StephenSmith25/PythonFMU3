
from pythonfmu3 import Fmi3Causality, Fmi3Variability, Dimension, Fmi3Slave, Fmi3Status, Float64, Int32, Int64, UInt64, String, Boolean

import numpy as np

SIZE = 10

TYPES = [UInt64, Float64, Boolean, Int32, Int64]
CAUSALITY = [Fmi3Causality.output, Fmi3Causality.input]

TYPE_MAP = {
    UInt64: np.uint64,
    Float64: np.float64,
    Int32: np.int32,
    Int64: np.int64,
    Boolean: bool
}

def var_names(var_type, causality):
    return f"{var_type.__name__.lower()}_{causality.name.lower()}"


def init_var(var_type, causality, array=True):
    if array:
        return np.zeros(SIZE, dtype=TYPE_MAP[var_type])
    else:
        return TYPE_MAP[var_type]()


def create_vars(self):
    dimensions = [Dimension(start=str(SIZE))]
    for var_type in TYPES:
      for causality in CAUSALITY:
        name = var_names(var_type, causality)
        if var_type == Float64:
            var = var_type(name, causality=causality, variability=Fmi3Variability.continuous, dimensions=dimensions)
        else:
            var = var_type(name, causality=causality, variability=Fmi3Variability.discrete, dimensions=dimensions)
        setattr(self, name, init_var(var_type, causality))
        self.register_variable(var)


def generate_data(self):
    for var_type in TYPES:
      causality = Fmi3Causality.output
      name = var_names(var_type, causality)
      var = getattr(self, name)
      if var_type == Boolean:
          data = [False, True, False, True, True, False, False, True, False, True]
          setattr(self, name, np.array(data).astype(bool))
      elif var_type == Int32 or var_type == Int64 or var_type == UInt64:
          data = [1,2,3,4,5,6,7,8,9,10]
          setattr(self, name, np.array(data).astype(TYPE_MAP[var_type]))
      else:
          data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
          setattr(self, name, np.array(data).astype(TYPE_MAP[var_type]))

class ArrayTypes(Fmi3Slave):
  

  def __init__(self, **kwargs):
      super().__init__(**kwargs)

      self.author = "Tester"
      self.description = "FMU with all basic types as arrays"

      self.time = 0.0

      self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
      
      create_vars(self)

      generate_data(self)
      

  def do_step(self, current_time: float, step_size: float) -> Fmi3Status:
      generate_data(self)
      return True

      
