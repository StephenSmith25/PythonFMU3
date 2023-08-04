from pythonfmu3.variables import Boolean, Integer, Real, ModelVariable, String

FMI2PY = dict((
    (Boolean, bool),
    (Integer, int),
    (Real, float),
    (String, str)
))
PY2FMI = dict([(v, k) for k, v in FMI2PY.items()])
