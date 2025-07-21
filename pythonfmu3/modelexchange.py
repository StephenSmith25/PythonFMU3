from abc import ABC, ABCMeta, abstractmethod

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
    """
    
    @abstractmethod
    def get_continuous_state_derivatives(self):
        """Return the continuous state derivatives of the model."""
        pass