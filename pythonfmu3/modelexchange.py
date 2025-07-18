from abc import ABC, abstractmethod

from .enums import Fmi3Interface

# model exchange mixin
class ModelExchange(ABC):
    INTERFACE = Fmi3Interface.modelExchange
    
    @abstractmethod
    def get_continuous_state_derivatives(self):
        """Return the continuous state derivatives of the model."""
        pass