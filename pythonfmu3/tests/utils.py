from pythonfmu3.variables import Boolean, Integer, UInt64, Real, ModelVariable, String
import ctypes
class UInt64ValType(int): pass


FMI2PY = dict((
    (Boolean, bool),
    (Integer, int),
    (Real, float),
    (String, str),
    (UInt64, UInt64ValType),
))
PY2FMI = dict([(v, k) for k, v in FMI2PY.items()])
