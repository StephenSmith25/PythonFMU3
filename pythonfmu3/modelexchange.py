from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass

@dataclass
class Fmi3UpdateDiscreteStatesResult:
    discreteStateNeedsUpdate: bool = False
    terminateSimulation: bool = False
    nominalsOfContinuousStatesChanged: bool = False
    valuesOfContinuousStatesChanged: bool = False
    nextEventTimeDefined: bool = False
    nextEventTime: float = 0.0

class RequireTimeMeta(ABCMeta):
    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        orig_init = cls.__init__
        def new_init(self, *args, **kwargs):
            orig_init(self, *args, **kwargs)
            if not hasattr(self, 'time'):
                raise AttributeError(f"{cls.__name__} must define 'self.time' in __init__")
        cls.__init__ = new_init


# model exchange mixin
class ModelExchange(ABC, metaclass=RequireTimeMeta):
    """
    Classes derived from ModelExchange must define a 'self.time' member variable.
    
    Required methods to override:
    - `get_continuous_state_derivatives`: Must return a list of continuous state derivatives.

    Optional methods:
    - `get_event_indicators`: Should return a list of event indicators.
    - `update_discrete_states`: Signify converged solution at current super-dense time instant.
    """
    
    @abstractmethod
    def get_continuous_state_derivatives(self):
        """Return the continuous state derivatives of the model."""
        pass
    
    def get_event_indicators(self):
        """Return the event indicators of the model."""
        return []
    
    def update_discrete_states(self):
        """Update the discrete states of the model."""
        return Fmi3UpdateDiscreteStatesResult()

    def get_nominals_of_continuous_states(self, size: int) -> list[float]:
        """Return the nominal values of the continuous states."""
        return [1.0] * size