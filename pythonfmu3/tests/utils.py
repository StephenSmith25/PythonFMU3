from pythonfmu3.variables import Boolean, Int32, UInt64, Float64, ModelVariable, String

class UInt64ValType(int): pass


FMI2PY = dict((
    (Boolean, bool),
    (Int32, int),
    (Float64, float),
    (String, str),
    (UInt64, UInt64ValType),
))
PY2FMI = dict([(v, k) for k, v in FMI2PY.items()])
