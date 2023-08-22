from xml.etree.ElementTree import Element

class BaseUnit(object):
    tag = "BaseUnit"
    base_units = {
        "kg": 0,
        "m": 0,
        "s": 0,
        "A": 0,
        "K": 0,
        "mol": 0,
        "cd": 0,
        "rad": 0,
    }

    def __init__(self, factor=1.0, offset=0.0, **kwargs) -> None:
        self._factor = factor
        self._offset = offset
        self._units = {**BaseUnit.base_units, **kwargs}

    @property
    def units(self):
        return {key: str(value) for key, value in self._units.items() if value != 0}

    def to_xml(self):
      """Convert the variable to XML node.

      Returns
          xml.etree.ElementTree.Element: XML node
      """
      attrib = dict()
      if self._factor != 1.0:
        attrib["factor"] = str(self._factor)
      if self._offset != 0.0:
        attrib["offset"] = str(self._offset)
      attrib.update(self.units)
      ele = Element(self.tag, attrib)
      return ele


class Unit(object):
    tag = "Unit"

    def __init__(self, name, **kwargs):
        self._name = name
        self._base_unit = BaseUnit(**kwargs)

    @property
    def name(self) -> str:
       return self._name

    def to_xml(self) -> Element:
      """Convert the variable to XML node.

      Returns
          xml.etree.ElementTree.Element: XML node
      """
      attrib = dict()
      attrib["name"] = self._name
      ele = Element(self.tag, attrib)
      ele.append(self._base_unit.to_xml())
      return ele
