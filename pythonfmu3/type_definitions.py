from enum import Enum
from typing import Any, Optional, List
from xml.etree.ElementTree import Element


class TypeDefinitions(object):
    tag = "TypeDefinitions"

    def __init__(self, types: List[Any]):
        self.types = types

    def to_xml(self) -> Element:
        """Convert the variable to XML node.

        Returns
            xml.etree.ElementTree.Element: XML node
        """
        attrib = dict()
        ele = Element(self.tag, attrib)
        for definition in self.types:
            ele.append(definition.to_xml())
        return ele


class Item(object):
    tag = "Item"

    def __init__(self, name: str, value: str, description: str = ""):
        self.__attrs = {
            "name": name,
            "value": value,
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


class EnumerationType(object):
    tag = "EnumerationType"

    def __init__(self, name: str, items = List[Item]):
        self.__attrs = {
            "name": name
        }
        self._items = items

    def name(self) -> str:
        return self.__attrs["name"]

    def to_xml(self) -> Element:
        """Convert the variable to XML node.

        Returns
            xml.etree.ElementTree.Element: XML node
        """
        element = Element(self.tag, self.__attrs)
        for item in self._items:
            element.append(item.to_xml())
        return element