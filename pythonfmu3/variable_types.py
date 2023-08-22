from enum import Enum
from typing import Optional
from xml.etree.ElementTree import Element

class VariableType(object):

    def __init__(self, tag, name, **kwargs):
        self._tag = tag
        self._attrs = {
            "name": name,
        }
        self._attrs.update(**kwargs)
    
    @property
    def name(self) -> str:
        """str: Variable name"""
        return self._attrs["name"]

    def to_xml(self) -> Element:
        """Convert the variable to XML node.

        Returns
            xml.etree.ElementTree.Element: XML node
        """
        attrib = dict()
        for key, value in self._attrs.items():
            if value is not None:
                attrib[key] = str(value.name if isinstance(value, Enum) else value)
        return Element(self._tag, attrib)

class Float64Type(VariableType):
    tag = "Float64Type"

    def __init__(self, name, **kwargs):
        super().__init__(self.tag, name, **kwargs)


class Item(object):
    tag = "Item"

    def __init__(self, name: str, value: int, description: str = "", **kwargs):
        self.__attrs = {
            "name": name,
            "value": str(value),
            "description": description
        }

    def name(self) -> str:
        return self.__attrs["name"]

    @property
    def value(self) -> str:
        return self.__attrs["value"]

    @property
    def description(self) -> Optional[str]:
        return self.__attrs["description"]

    def to_xml(self) -> Element:
        """Convert the variable to XML node.

        Returns
            xml.etree.ElementTree.Element: XML node
        """
        attrib = dict()
        for key, value in self.__attrs.items():
            if value is not None:
                attrib[key] = str(value.name if isinstance(value, Enum) else value)
        return Element(self.tag, attrib)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}" \
               f"(name={self.name}, " \
               f"value={self.value}, " \
               f"description={self.description})"

class EnumerationType(VariableType):
    tag = "EnumerationType"

    def __init__(self, name: str, values: Optional[Enum] = None,  **kwargs):
        super().__init__(self.tag, name, **kwargs)
        self._items = {}
        
        for val in values:
            self.add_value(name = val.name, value = val.value)

    def add_value(self, name: str, value: int, description: str = "", **kwargs):
        self._items[name] = Item(name, value, description, **kwargs)
    
    def get_value(self, name):
        return self._items[name]

    def to_xml(self) -> Element:
        """Convert the variable to XML node.

        Returns
            xml.etree.ElementTree.Element: XML node
        """
        parent = super().to_xml()
        for _, item in self._items.items():
            parent.append(item.to_xml())
        return parent