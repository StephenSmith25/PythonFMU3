from abc import ABC, abstractmethod

from .enums import Fmi3Interface

class ModelExchange(ABC):
    INTERFACE = Fmi3Interface.modelExchange

    
    @abstractmethod
    def get_continuous_states(self):
        """Return the continuous states of the model."""
        pass