from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Float64, Int64, Enumeration, Fmi3Initial, TypeDefinitions, EnumerationType, Item

import enum


class Enum(Fmi3Slave):

    author = "..."
    description = "Enum"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.time = 0.0
        self.x = 0.0

        items = [Item(name="Option_1", value="1", description="first"), 
                 Item(name="Option_2", value="2", description="second")]

        enumerations = EnumerationType(name="Option", items=items)
        Options = enum.Enum('Options', {'Option_1': 1, 'Option_2': 2})
        self.option = Options.Option_1
        self.type_definitions = TypeDefinitions([enumerations])

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("x", causality=Fmi3Causality.output, initial=Fmi3Initial.calculated))
        self.register_variable(Enumeration("option", declared_type="Option", start=1, causality=Fmi3Causality.input,
                                           getter=lambda: self.option.value, setter=lambda v: setattr(self, "option", Options(v))))

    def do_step(self, current_time, step_size):
        self.x += 1.0
        return True
