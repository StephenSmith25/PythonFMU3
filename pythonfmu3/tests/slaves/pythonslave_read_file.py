from pythonfmu3.fmi3slave import Fmi3Slave, Fmi3Causality, Fmi3Variability, String, DefaultExperiment, Float64


class PythonSlaveReadFile(Fmi3Slave):

    default_experiment = DefaultExperiment(start_time=0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with (open(f'{self.resources}/hello.txt', 'r')) as file:
            data = file.read()

        self.time = 0

        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(
            String("file_content", getter=lambda: data,
                   causality=Fmi3Causality.output,
                   variability=Fmi3Variability.constant))

    def do_step(self, current_time, step_size):
        return True
