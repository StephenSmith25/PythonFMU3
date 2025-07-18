from abc import ABC, abstractmethod

from .enums import Fmi3Interface

# co-simulation mixin
class CoSimulation(ABC):
    INTERFACE = Fmi3Interface.coSimulation

    @abstractmethod
    def do_step(self, current_time: float, step_size: float):
        pass