from abc import ABC, abstractmethod

# model exchange mixin
class ModelExchange(ABC):
    
    @abstractmethod
    def get_continuous_state_derivatives(self):
        """Return the continuous state derivatives of the model."""
        pass