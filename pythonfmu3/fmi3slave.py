"""Define the abstract facade class."""
import json
import ctypes
import datetime
from abc import ABC, abstractmethod
from collections import OrderedDict, namedtuple
from pathlib import Path
from typing import Any, ClassVar, Dict, List, NamedTuple, Optional
from uuid import uuid1
from xml.etree.ElementTree import Element, SubElement

from .logmsg import LogMsg
from .default_experiment import DefaultExperiment
from ._version import __version__ as VERSION
from .enums import Fmi3Type, Fmi3Status, Fmi3Causality, Fmi3Initial, Fmi3Variability
from .variables import Boolean, Enumeration, Int32, Int64, UInt64, Float64, ModelVariable, String
from .variable_types import VariableType
from .unit import Unit

ModelOptions = namedtuple("ModelOptions", ["name", "value", "cli"])

FMI3_MODEL_OPTIONS: List[ModelOptions] = [
    ModelOptions("needsExecutionTool", True, "no-external-tool"),
    ModelOptions("canHandleVariableCommunicationStepSize", True, "no-variable-step"),
    ModelOptions("canBeInstantiatedOnlyOncePerProcess", False, "only-one-per-process"),
    ModelOptions("canGetAndSetFMUState", False, "handle-state"),
    ModelOptions("canSerializeFMUState", False, "serialize-state")
]

class Fmi3StepResult(NamedTuple):
    status: Fmi3Status = Fmi3Status.ok
    eventHandlingNeeded: bool = False
    terminateSimulation: bool = False
    earlyReturn: bool = False

class Fmi3Slave(ABC):
    """Abstract facade class to execute Python through FMI standard."""

    # Dictionary of (category, description) entries
    log_categories: Dict[str, str] = {
        "logStatusWarning": "Log messages with fmi3Warning status.",
        "logStatusDiscard": "Log messages with fmi3Discard status.",
        "logStatusError": "Log messages with fmi3Error status.",
        "logStatusFatal": "Log messages with fmi3Fatal status.",
        "logAll": "Log all messages."
    }

    def __init__(self, **kwargs):
        self.vars = OrderedDict()
        self.instance_name = kwargs["instance_name"]
        self.resources = kwargs.get("resources", None)
        self.visible = kwargs.get("visible", False)
        self.log_queue = []

        self.guid = uuid1()
        self.author: Optional[str] = None
        self.license: Optional[str] = None
        self.version: Optional[str] = None
        self.copyright: Optional[str] = None
        self.modelName: Optional[str] = self.__class__.__name__
        self.description: Optional[str] = None
        self.default_experiment: Optional[DefaultExperiment] = None

        self.type_definitions: Dict[str, VariableType] = {}
        self.units: Dict[str, Unit] = {}

    def to_xml(self, model_options: Dict[str, str] = dict()) -> Element:
        """Build the XML representation of the model.
        
        Args:
            model_options (Dict[str, str]) : FMU model options
        
        Returns:
            (xml.etree.TreeElement.Element) XML description of the FMU
        """

        t = datetime.datetime.now(datetime.timezone.utc)
        date_str = t.isoformat(timespec="seconds")

        attrib = dict(
            fmiVersion="3.0",
            modelName=self.modelName,
            instantiationToken=f"{self.guid!s}",
            generationTool=f"PythonFMU3 {VERSION}",
            generationDateAndTime=date_str,
            variableNamingConvention="structured"
        )
        if self.description is not None:
            attrib["description"] = self.description
        if self.author is not None:
            attrib["author"] = self.author
        if self.license is not None:
            attrib["license"] = self.license
        if self.version is not None:
            attrib["version"] = self.version
        if self.copyright is not None:
            attrib["copyright"] = self.copyright

        root = Element("fmiModelDescription", attrib)

        options = dict()
        for option in FMI3_MODEL_OPTIONS:
            value = model_options.get(option.name, option.value)
            options[option.name] = str(value).lower()
        options["modelIdentifier"] = self.modelName
        options["canNotUseMemoryManagementFunctions"] = "true"

        SubElement(root, "CoSimulation", attrib=options)

        if self.units:
            unit_defs = SubElement(root, "UnitDefinitions")
            for _, unit in self.units.items():
                unit_defs.append(unit.to_xml())

        if self.type_definitions:
            type_defs = SubElement(root, "TypeDefinitions")
            for _, val in self.type_definitions.items():
                type_defs.append(val.to_xml())

        if len(self.log_categories) > 0:
            categories = SubElement(root, "LogCategories")
            for category, description in self.log_categories.items():
                categories.append(
                    Element(
                        "Category",
                        attrib={"name": category, "description": description},
                    )
                )

        if self.default_experiment is not None:
            attrib = dict()
            if self.default_experiment.start_time is not None:
                attrib["startTime"] = str(self.default_experiment.start_time)
            if self.default_experiment.stop_time is not None:
                attrib["stopTime"] = str(self.default_experiment.stop_time)
            if self.default_experiment.step_size is not None:
                attrib["stepSize"] = str(self.default_experiment.step_size)
            if self.default_experiment.tolerance is not None:
                attrib["tolerance"] = str(self.default_experiment.tolerance)
            SubElement(root, "DefaultExperiment", attrib)
            
        variables = SubElement(root, "ModelVariables")
        for v in self.vars.values():
            if ModelVariable.requires_start(v):
                self.__apply_start_value(v)
            variables.append(v.to_xml())

        structure = SubElement(root, "ModelStructure")
        outputs = list(
            filter(lambda v: v.causality == Fmi3Causality.output, self.vars.values())
        )

        continuous_state_derivatives = list(
            filter(lambda v: v.variability == Fmi3Variability.continuous and (isinstance(v, Float64) and v.derivative is not None), self.vars.values())
        )

        allowed_variability = [None, Fmi3Initial.approx, Fmi3Initial.calculated]
        initial_unknown = list(
            filter(lambda v: (v.causality == Fmi3Causality.output and (v.initial in allowed_variability))
                              or v.causality == Fmi3Causality.calculatedParameter
                              or v in continuous_state_derivatives and v.initial in allowed_variability
                              or v.variability == Fmi3Variability.continuous and v.initial in allowed_variability and v.causality != Fmi3Causality.independent, self.vars.values())
        )

        for v in outputs:
            SubElement(structure, "Output", attrib=dict(valueReference=str(v.value_reference)))

        for v in continuous_state_derivatives:
            SubElement(structure, "ContinuousStateDerivative", attrib=dict(valueReference=str(v.value_reference)))

        for v in initial_unknown:
            SubElement(structure, "InitialUnknown", attrib=dict(valueReference=str(v.value_reference)))
        


        return root

    def __apply_start_value(self, var: ModelVariable):
        vrs = [var.value_reference]
        if isinstance(var, Int32):
            refs = self.get_int32(vrs)
        elif isinstance(var, (Enumeration, Int64)):
            refs = self.get_int64(vrs)
        elif isinstance(var, UInt64):
            refs = [val.value for val in self.get_uint64(vrs)]
        elif isinstance(var, Float64):
            refs = self.get_float64(vrs)
        elif isinstance(var, Boolean):
            refs = self.get_boolean(vrs)
        elif isinstance(var, String):
            refs = self.get_string(vrs)
        else:
            raise Exception(f"Unsupported type {type(var)}!")
        var.start = refs if len(getattr(var, "dimensions", [])) > 0 else refs[0]

    def register_variable(self, var: ModelVariable, nested: bool = True, var_type: Any = None):
        """Register a variable as FMU interface.
        
        Args:
            var (ModelVariable): The variable to be registered
            nested (bool): Optional, does the "." in the variable name reflect an object hierarchy to access it? Default True
        """
        variable_reference = len(self.vars)
        self.vars[variable_reference] = var
        # Set the unique value reference
        var.value_reference = variable_reference
        owner = self
        if var.getter is None and nested and "." in var.name:
            split = var.name.split(".")
            split.pop(-1)
            for s in split:
                owner = getattr(owner, s)
        if var.getter is None:
            if hasattr(var, "dimensions") and len(var.dimensions) > 0:
                var.getter = lambda: getattr(owner, var.local_name).flatten().tolist()
            else:
                var.getter = lambda: getattr(owner, var.local_name)
        if var.setter is None and hasattr(owner, var.local_name) and var.variability != Fmi3Variability.constant:
            if hasattr(var, "dimensions") and len(var.dimensions) > 0:
                import numpy as np
                var.setter = lambda v: setattr(owner, var.local_name, np.reshape(v, newshape=getattr(owner, var.local_name).shape))
            else:
                var.setter = lambda v: setattr(owner, var.local_name, v)
        
        if var_type:
            self.type_definitions[var_type.name] = var_type
            var.declared_type = var_type.name

    def setup_experiment(self, start_time: float):
        pass

    def register_units(self, units: List[Unit]):
        for unit in units:
            self.units[unit.name] = unit

    def enter_initialization_mode(self):
        pass

    def exit_initialization_mode(self):
        pass

    @abstractmethod
    def do_step(self, current_time: float, step_size: float) -> Fmi3StepResult:
        pass

    def terminate(self):
        pass

    def get_int32(self, vrs: List[int]) -> List[int]:
        refs = list()
        for vr in vrs:
            var = self.vars[vr]
            if isinstance(var, Int32):
                refs.append(int(var.getter()))
            else:
                raise TypeError(
                    f"Variable with valueReference={vr} is not of type Integer!"
                )
        return refs
    
    def get_int64(self, vrs: List[int]) -> List[int]:
        refs = list()
        for vr in vrs:
            var = self.vars[vr]
            if isinstance(var, (Enumeration, Int64)):
                refs.append(int(var.getter()))
            else:
                raise TypeError(
                    f"Variable with valueReference={vr} is not of type Int64!"
                )
        return refs

    def get_uint64(self, vrs: List[int]) -> List[ctypes.c_uint64]:
        refs = list()
        for vr in vrs:
            var = self.vars[vr]
            if isinstance(var, UInt64):
                val = var.getter()
                refs.append(val if isinstance(val, ctypes.c_uint64) else ctypes.c_uint64(val))
            else:
                raise TypeError(
                    f"Variable with valueReference={vr} is not of type UInt64!"
                )
        return refs

    def get_float64(self, vrs: List[int]) -> List[float]:
        refs = list()
        for vr in vrs:
            var = self.vars[vr]
            if isinstance(var, Float64):
                if len(var.dimensions) == 0:
                    refs.append(float(var.getter()))
                else:
                    refs.extend(var.getter())
            else:
                raise TypeError(
                    f"Variable with valueReference={vr} is not of type Real!"
                )
        return refs

    def get_boolean(self, vrs: List[int]) -> List[bool]:
        refs = list()
        for vr in vrs:
            var = self.vars[vr]
            if isinstance(var, Boolean):
                refs.append(bool(var.getter()))
            else:
                raise TypeError(
                    f"Variable with valueReference={vr} is not of type Boolean!"
                )
        return refs

    def get_string(self, vrs: List[int]) -> List[str]:
        refs = list()
        for vr in vrs:
            var = self.vars[vr]
            if isinstance(var, String):
                refs.append(str(var.getter()))
            else:
                raise TypeError(
                    f"Variable with valueReference={vr} is not of type String!"
                )
        return refs

    def set_int32(self, vrs: List[int], values: List[int]):
        for vr, value in zip(vrs, values):
            var = self.vars[vr]
            if isinstance(var, Int32):
                var.setter(value)
            else:
                raise TypeError(
                    f"Variable with valueReference={vr} is not of type Integer!"
                )
                
    def set_int64(self, vrs: List[int], values: List[int]):
        for vr, value in zip(vrs, values):
            var = self.vars[vr]
            if isinstance(var, (Enumeration, Int64)):
                var.setter(value)
            else:
                raise TypeError(
                    f"Variable with valueReference={vr} is not of type Integer!"
                )

    def set_uint64(self, vrs: List[int], values: List[int]):
        for vr, value in zip(vrs, values):
            var = self.vars[vr]
            if isinstance(var, UInt64):
                var.setter(value)
            else:
                raise TypeError(
                    f"Variable with valueReference={vr} is not of type UInt64!"
                )

    def set_float64(self, vrs: List[int], values: List[float]):
        offset = 0
        for vr in vrs:
            var = self.vars[vr]
            if isinstance(var, Float64):
                size = var.size(self.vars)
                if size > 1:
                    var.setter(values[offset:offset+size])
                else:
                    var.setter(values[offset])
                offset += size
            else:
                raise TypeError(
                    f"Variable with valueReference={vr} is not of type Real!"
                )

    def set_boolean(self, vrs: List[int], values: List[bool]):
        for vr, value in zip(vrs, values):
            var = self.vars[vr]
            if isinstance(var, Boolean):
                var.setter(value)
            else:
                raise TypeError(
                    f"Variable with valueReference={vr} is not of type Boolean!"
                )

    def set_string(self, vrs: List[int], values: List[str]):
        for vr, value in zip(vrs, values):
            var = self.vars[vr]
            if isinstance(var, String):
                var.setter(value)
            else:
                raise TypeError(
                    f"Variable with valueReference={vr} is not of type String!"
                )

    def _get_fmu_state(self) -> Dict[str, Any]:
        state = dict()
        for var in self.vars.values():
            state[var.name] = var.getter()
        return state

    def _set_fmu_state(self, state: Dict[str, Any]):
        vars_by_name = dict([(v.name, v) for v in self.vars.values()])
        for name, value in state.items():
            if name not in vars_by_name:
                setattr(self, name, value)
            else:
                v = vars_by_name[name]
                if v.setter is not None:
                    v.setter(value)

    @staticmethod
    def _fmu_state_to_bytes(state: Dict[str, Any]) -> bytes:
        return json.dumps(state).encode("utf-8")

    @staticmethod
    def _fmu_state_from_bytes(state: bytes) -> Dict[str, Any]:
        return json.loads(state.decode("utf-8"))

    def _get_log_queue(self):
        return self.log_queue

    def log(
        self,
        msg: str,
        status: Fmi3Status = Fmi3Status.ok,
        category: Optional[str] = None,
        debug: bool = False
    ):
        """Log a message to the FMU logger.
        
        Args:
            msg (str) : Log message
            status (Fmi3Status) : Optional, message status (default ok)
            category (str or None) : Optional, message category (default derived from status)
            debug (bool) : Optional, is this a debug message (default False)
        """
        if category is None:
            category = f"logStatus{status.name.capitalize()}"
            if category not in self.log_categories:
                category = "logAll"
        log_msg = LogMsg(status, category, msg, debug)
        self.log_queue.append(log_msg)
