from abc import ABC, abstractmethod

# co-simulation mixin
class CoSimulation(ABC):

    @abstractmethod
    def do_step(self, current_time: float, step_size: float):
        pass