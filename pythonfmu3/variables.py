"""Classes describing interface variables."""
from abc import ABC
from enum import Enum
import importlib
from typing import Any, Optional, List
from xml.etree.ElementTree import Element, SubElement
from collections import ChainMap
from functools import reduce  

from .enums import Fmi3Causality, Fmi3Initial, Fmi3Variability

def check_numpy():
    try:
        importlib.import_module('numpy')
    except ModuleNotFoundError:
        raise ModuleNotFoundError("Numpy is not installed, it is required for Array support")

class ModelVariable(ABC):
    """Abstract FMI model variable definition.

    Args:
        name (str): Variable name
        causality (:obj:`Fmi3Causality`, optional): Variable causality
        description (str, optional): Variable description
        initial (:obj:`Fmi3Initial`, optional): Variable initial status
        variability (:obj:`Fmi3Variability`, optional): Variable variability
    """
    def __init__(
        self,
        name: str,
        causality: Optional[Fmi3Causality] = None,
        description: Optional[str] = None,
        initial: Optional[Fmi3Initial] = None,
        variability: Optional[Fmi3Variability] = None,
        declared_type: Optional[str] = None,
        getter: Any = None,
        setter: Any = None
    ):
        self.getter = getter
        self.setter = setter
        self._type = None
        self.local_name = name.split(".")[-1]
        self.__attrs = {
            "name": name,
            "valueReference": None,
            "description": description,
            "causality": causality,
            "variability": variability,
            "initial": initial,
            "declaredType": declared_type,
            # 'canHandleMultipleSetPerTimeInstant': # Only for ME
        }
        self._extras = {}

    @property
    def causality(self) -> Optional[Fmi3Causality]:
        """:obj:`Fmi3Causality` or None: Variable causality - None if not set"""
        return self.__attrs["causality"]

    @property
    def description(self) -> Optional[str]:
        """str or None: Variable description - None if not set"""
        return self.__attrs["description"]

    @property
    def initial(self) -> Optional[Fmi3Initial]:
        """:obj:`Fmi3Initial` or None: Variable initial status - None if not set"""
        return self.__attrs["initial"]

    @property
    def name(self) -> str:
        """str: Variable name"""
        return self.__attrs["name"]

    @property
    def value_reference(self) -> int:
        """int: Variable reference index"""
        return self.__attrs["valueReference"]

    @value_reference.setter
    def value_reference(self, value: int):
        if self.__attrs["valueReference"] is not None:
            raise RuntimeError("Value reference already set.")
        self.__attrs["valueReference"] = value

    @property
    def declared_type(self) -> str:
        """str: declared type"""
        return self.__attrs["declaredType"]

    @declared_type.setter
    def declared_type(self, value: str):
        if self.__attrs["declaredType"] is not None:
            raise RuntimeError("Declared type already set.")
        self.__attrs["declaredType"] = value
    
    @property
    def variability(self) -> Optional[Fmi3Variability]:
        """:obj:`Fmi3Variability` or None: Variable variability - None if not set"""
        return self.__attrs["variability"]
    
    @staticmethod
    def requires_start(v: 'ModelVariable') -> bool:
        """Test if a variable requires a start attribute

        Returns:
            True if successful, False otherwise
        """
        return (
            v.initial == Fmi3Initial.exact
            or v.initial == Fmi3Initial.approx
            or v.causality == Fmi3Causality.input
            or v.causality == Fmi3Causality.parameter
            or v.variability == Fmi3Variability.constant
        )

    def to_xml(self) -> Element:
        """Convert the variable to XML node.

        Returns
            xml.etree.ElementTree.Element: XML node
        """
        attrib = dict()
        for key, value in ChainMap(self._extras, self.__attrs).items():
            if value is not None:
                attrib[key] = str(value.name if isinstance(value, Enum) else value)
        return Element(self._type, attrib)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}" \
               f"(name={self.name}, " \
               f"causality={self.causality}, " \
               f"variability={self.variability})"

class Start(object):
    def __init__(self, startValue):
        self.value = startValue
    
    def to_xml(self) -> Element:
        attrib = dict()
        attrib["value"] = self.value
        return Element("Start", attrib)


class Dimension(object):
    def __init__(self, start: str = "", valueReference: str = ""):
        if start and valueReference and any((start, valueReference)):
            raise RuntimeError("start and valueReference attributes are mutally exclusive for Dimension element")
        
        self.start = start
        self.value_reference = valueReference

    def size(self, vars : List[ModelVariable]):
        if self.start:
            return self.start
        else:
            result = next((value for vr, value in vars.items() if vr == int(self.value_reference)), None)  
            return result.getter()

    def to_xml(self) -> Element:
        attrib = dict()

        if self.start:
            attrib["start"] = self.start
        else:
            attrib['valueReference'] = self.value_reference
        ele = Element("Dimension", attrib)
        return ele

class Float64(ModelVariable):
    def __init__(self, name: str, start: Optional[Any] = None, derivative: Optional[Any] = None, dimensions: List[Dimension] = [], unit: Optional[str] = None, **kwargs):
        super().__init__(name, **kwargs)
        self.__attrs = {"start": start, "derivative": derivative}
        self._type = "Float64"
        self._unit = unit
        if dimensions:
            check_numpy()
        self.__dimensions = dimensions

    @property
    def start(self) -> Optional[Any]:
        return self.__attrs["start"]

    @start.setter
    def start(self, value: float):
        self.__attrs["start"] = value
    
    @property
    def unit(self) -> Optional[Any]:
        return self._unit

    @unit.setter
    def unit(self, value: str):
        self._unit = value

    @property
    def derivative(self):
        return self.__attrs["derivative"]
    
    @property
    def dimensions(self) -> List[Dimension]:
        return self.__dimensions


    def to_xml(self) -> Element:
        attrib = dict()
        for key, value in self.__attrs.items():
            if value is not None:
                # In order to not loose precision, a number of this type should be
                # stored on an XML file with at least 16 significant digits
                output = ""
                if len(self.dimensions) > 0:
                    output = " ".join([f"{val:.16g}" for val in value])
                else:
                    output = f"{value:.16g}"
                attrib[key] = output

        if self.unit:
            attrib["unit"] = self.unit

        self._extras = attrib
        parent = super().to_xml()

        for dimension in self.__dimensions:
            parent.append(dimension.to_xml())

        return parent
    
    def size(self, vars):
        return reduce(lambda x, dim: x * int(dim.size(vars)), self.__dimensions, 1)


class Int32(ModelVariable):
    def __init__(self, name: str, start: Optional[Any] = None, **kwargs):
        super().__init__(name, **kwargs)
        self.__attrs = {"start": start}
        self._type = "Int32";

    @property
    def start(self) -> Optional[Any]:
        return self.__attrs["start"]

    @start.setter
    def start(self, value: int):
        self.__attrs["start"] = value

    def to_xml(self) -> Element:
        attrib = dict()
        for key, value in self.__attrs.items():
            if value is not None:
                attrib[key] = str(value)
        self._extras = attrib
        parent = super().to_xml()

        return parent
        
class Int64(ModelVariable):
    def __init__(self, name: str, start: Optional[Any] = None, **kwargs):
        super().__init__(name, **kwargs)
        self.__attrs = {"start": start}
        self._type = "Int64";

    @property
    def start(self) -> Optional[Any]:
        return self.__attrs["start"]

    @start.setter
    def start(self, value: int):
        self.__attrs["start"] = value

    def to_xml(self) -> Element:
        attrib = dict()
        for key, value in self.__attrs.items():
            if value is not None:
                attrib[key] = str(value)
        self._extras = attrib
        parent = super().to_xml()

        return parent

class UInt64(ModelVariable):
    def __init__(self, name: str, start: Optional[Any] = None, **kwargs):
        super().__init__(name, **kwargs)
        self.__attrs = {"start": start}
        self._type = "UInt64";

    @property
    def start(self) -> Optional[Any]:
        return self.__attrs["start"]

    @start.setter
    def start(self, value: int):
        self.__attrs["start"] = value

    def to_xml(self) -> Element:
        attrib = dict()
        for key, value in self.__attrs.items():
            if value is not None:
                attrib[key] = str(value)
        self._extras = attrib
        parent = super().to_xml()

        return parent

class Boolean(ModelVariable):
    def __init__(self, name: str, start: Optional[Any] = None, **kwargs):
        super().__init__(name, **kwargs)
        self.__attrs = {"start": start}
        self._type = "Boolean"

    @property
    def start(self) -> Optional[Any]:
        return self.__attrs["start"]

    @start.setter
    def start(self, value: float):
        self.__attrs["start"] = value

    def to_xml(self) -> Element:
        attrib = dict()
        for key, value in self.__attrs.items():
            if value is not None:
                attrib[key] = str(value).lower()
        self._extras = attrib
        parent = super().to_xml()

        return parent


class String(ModelVariable):
    def __init__(self, name: str, start: Optional[Any] = None, **kwargs):
        super().__init__(name, **kwargs)
        self.__attrs = dict()
        self._type = "String"
        self._start = Start(start)

    @property
    def start(self) -> Optional[Any]:
        return self._start.value

    @start.setter
    def start(self, value: float):
        self._start.value = value

    def to_xml(self) -> Element:
        attrib = dict()
        for key, value in self.__attrs.items():
            if value is not None:
                attrib[key] = str(value)
        self._extras = attrib
        parent = super().to_xml()
        
        if self.start is not None:
            parent.append(self._start.to_xml())

        return parent
    
class Enumeration(ModelVariable):
    def __init__(self, name: str, start: Optional[Any] = None, declared_type: Optional[Any] = None, **kwargs):
        super().__init__(name, **kwargs)
        self.__attrs = {"start": start, "declaredType": declared_type}
        self._type = "Enumeration"

    @property
    def start(self) -> Optional[Any]:
        return self.__attrs["start"]

    @start.setter
    def start(self, value: float):
        self.__attrs["start"] = value

    @property
    def declared_type(self) -> Optional[Any]:
        return self.__attrs["declaredType"]

    @declared_type.setter
    def declared_type(self, value: float):
        self.__attrs["declaredType"] = value

    def to_xml(self) -> Element:
        attrib = dict()
        for key, value in self.__attrs.items():
            if value is not None:
                attrib[key] = str(value)
        self._extras = attrib
        parent = super().to_xml()

        return parent
