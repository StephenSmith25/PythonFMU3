from pythonfmu3 import Fmi3Causality, Fmi3Variability, Fmi3Slave, Float64, Enumeration, Fmi3Initial, EnumerationType

import enum


class Enum(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.author = "..."
        self.description = "Enum"

        self.time = 0.0
        self.x = 0.0

        Options = enum.Enum('Options', {'Option_1': 1, 'Option_2': 2})
        enum_type = EnumerationType(name="Option", values=Options)
        self.option = Options.Option_1

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("x", causality=Fmi3Causality.output, initial=Fmi3Initial.calculated))
        self.register_variable(Enumeration("option", declared_type="Option", start=1, causality=Fmi3Causality.input,
                                           getter=lambda: self.option.value, setter=lambda v: setattr(self, "option", Options(v))), var_type=enum_type)

    def do_step(self, current_time, step_size):
        self.x += 1.0
        return True
