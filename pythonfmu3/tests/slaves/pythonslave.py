from pythonfmu3.fmi3slave import Fmi3Slave, Fmi3Causality, Fmi3Variability, Int32, Float64, Boolean, String


class Container:
    pass


class PythonSlave(Fmi3Slave):

    author = "John Doe"
    description = "A simple description"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.intParam = 42
        self.intOut = 23
        self.realOut = 3.0
        self.booleanVariable = True
        self.stringVariable = "Hello World!"
        self.realIn = 2. / 3.
        self.booleanParameter = False
        self.stringParameter = "dog"
        self.time = 0

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(
            Int32("intParam", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable))
        self.register_variable(Float64("realIn", causality=Fmi3Causality.input))
        self.register_variable(
            Boolean("booleanParameter", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable))
        self.register_variable(
            String("stringParameter", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable))

        self.register_variable(Int32("intOut", causality=Fmi3Causality.output))
        self.register_variable(Float64("realOut", causality=Fmi3Causality.output))
        self.register_variable(Boolean("booleanVariable", causality=Fmi3Causality.local))
        self.register_variable(String("stringVariable", causality=Fmi3Causality.local))

        self.container = Container()
        self.container.someReal = 99.0
        self.container.subContainer = sub = Container()
        sub.someInteger = -15
        self.register_variable(
            Float64("container.someReal", causality=Fmi3Causality.parameter, variability=Fmi3Variability.tunable))
        self.register_variable(
            Int32("container.subContainer.someInteger", causality=Fmi3Causality.parameter,
                    variability=Fmi3Variability.tunable))

    def do_step(self, current_time, step_size):
        self.realOut = current_time + step_size
        return True
