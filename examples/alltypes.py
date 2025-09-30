from pythonfmu3 import Fmi3Causality, Fmi3Variability, Dimension, Fmi3Slave, Fmi3Status, Float64, Int32, Int64, UInt64, String, Boolean


TYPES = [UInt64, Float64, Boolean, Int32, Int64]
CAUSALITY = [Fmi3Causality.output, Fmi3Causality.input]
type_map = {
    UInt64: int,
    Float64: float,
    Int32: int,
    Int64: int,
    Boolean: bool
}

def var_names(var_type, causality):
    return f"{var_type.__name__.lower()}_{causality.name.lower()}"
  
def init_var(var_type, causality):
    return type_map[var_type]()
  
def create_vars(self):
    for var_type in TYPES:
      for causality in CAUSALITY:
        name = var_names(var_type, causality)
        if var_type == Float64:
            var = var_type(name, causality=causality, variability=Fmi3Variability.continuous)
        else:
            var = var_type(name, causality=causality, variability=Fmi3Variability.discrete)
        setattr(self, name, init_var(var_type, causality))
        self.register_variable(var)

class AllTypes(Fmi3Slave):

  def __init__(self, **kwargs):
      super().__init__(**kwargs)

      self.author = "Stephen Smith"
      self.description = "All types example"
      
      self.time = 0.0

      self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))

      create_vars(self)
  

  def do_step(self, current_time: float, step_size: float) -> Fmi3Status:
      # feedthrough
      for var_type in TYPES:
        input_var = getattr(self, var_names(var_type, Fmi3Causality.input))
        setattr(self, var_names(var_type, Fmi3Causality.output), input_var)
    
      return True
