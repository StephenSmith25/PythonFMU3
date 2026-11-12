
#include "pythonfmu/IPyState.hpp"
#include "pythonfmu/PySlaveInstance.hpp"

#include "pythonfmu/PyState.hpp"

#include "cppfmu/cppfmu_cs.hpp"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <mutex>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace pythonfmu
{

namespace
{

// Holds the GIL for the lifetime of the object. Releasing in the destructor guarantees
// the GIL is given back on every exit path, including C++ exceptions.
class GilGuard
{
public:
    GilGuard()
        : state_(PyGILState_Ensure())
    { }
    ~GilGuard() { PyGILState_Release(state_); }
    GilGuard(const GilGuard&) = delete;
    GilGuard& operator=(const GilGuard&) = delete;

private:
    PyGILState_STATE state_;
};

// Owning reference to a PyObject (Py_XDECREF on destruction).
// Must only be destroyed while the GIL is held; declare it after the GilGuard.
class PyRef
{
public:
    explicit PyRef(PyObject* obj = nullptr)
        : obj_(obj)
    { }
    ~PyRef() { Py_XDECREF(obj_); }
    PyRef(const PyRef&) = delete;
    PyRef& operator=(const PyRef&) = delete;
    PyRef(PyRef&& other) noexcept
        : obj_(other.release())
    { }

    PyObject* get() const { return obj_; }
    PyObject* release()
    {
        PyObject* tmp = obj_;
        obj_ = nullptr;
        return tmp;
    }
    explicit operator bool() const { return obj_ != nullptr; }

private:
    PyObject* obj_;
};

template<typename F>
auto py_safe_run(F&& f) -> decltype(f())
{
    GilGuard gil;
    return f();
}

// Reads the first two lines of resources/slavemodule.txt: the module name and
// (for FMUs built by newer versions of PythonFMU3) the name of the slave class.
std::pair<std::string, std::string> readSlaveModuleInfo(const std::string& fileName)
{
    std::ifstream infile(fileName);
    if (!infile) {
        throw cppfmu::FatalError(("Unable to open " + fileName).c_str());
    }
    std::string moduleName, className;
    std::getline(infile, moduleName);
    std::getline(infile, className);
    auto trim = [](std::string& s) {
        const auto ws = " \t\r\n";
        s.erase(s.find_last_not_of(ws) + 1);
        s.erase(0, s.find_first_not_of(ws));
    };
    trim(moduleName);
    trim(className);
    return {moduleName, className};
}

// Fallback for FMUs built by older versions that do not record the class name.
std::string findClassName(const std::string& fileName)
{
    std::string line;
    std::ifstream infile(fileName);
    const std::regex re(R"(^class (\w+)\(([^)]*\bFmi3Slave(?:Base)?\b[^)]*)\)\s*:)");
    while (std::getline(infile, line)) {
        std::smatch m;
        if (std::regex_search(line, m, re)) {
            return m[1];
        }
    }
    return "";
}

// Returns nullptr (with a Python error set) on failure.
PyObject* makeVrList(const cppfmu::FMIValueReference* vr, std::size_t nvr)
{
    PyRef list(PyList_New(static_cast<Py_ssize_t>(nvr)));
    if (!list) return nullptr;
    for (std::size_t i = 0; i < nvr; i++) {
        PyObject* item = PyLong_FromUnsignedLong(vr[i]);
        if (item == nullptr) return nullptr;
        PyList_SetItem(list.get(), static_cast<Py_ssize_t>(i), item); // steals item
    }
    return list.release();
}

template<typename T, typename Convert>
PyObject* makeValueList(const T* values, std::size_t n, Convert convert)
{
    PyRef list(PyList_New(static_cast<Py_ssize_t>(n)));
    if (!list) return nullptr;
    for (std::size_t i = 0; i < n; i++) {
        PyObject* item = convert(values[i]);
        if (item == nullptr) return nullptr;
        PyList_SetItem(list.get(), static_cast<Py_ssize_t>(i), item); // steals item
    }
    return list.release();
}

PyObject* makeString(cppfmu::FMIString s)
{
    if (s == nullptr) {
        Py_RETURN_NONE;
    }
    return PyUnicode_FromString(s);
}

std::string toUtf8(PyObject* str)
{
    PyRef bytes(str ? PyUnicode_AsEncodedString(str, "utf-8", "replace") : nullptr);
    const char* data = bytes ? PyBytes_AsString(bytes.get()) : nullptr;
    if (data == nullptr) {
        PyErr_Clear();
        return {};
    }
    return data;
}

// Formats the pending Python exception, including its traceback, and clears it.
std::string fetchPythonError()
{
    PyObject *type = nullptr, *value = nullptr, *traceback = nullptr;
    PyErr_Fetch(&type, &value, &traceback);
    if (type == nullptr) {
        return "unknown error (no Python exception set)";
    }
    PyErr_NormalizeException(&type, &value, &traceback);
    PyRef pType(type), pValue(value), pTraceback(traceback);

    std::string result;
    PyRef tbModule(PyImport_ImportModule("traceback"));
    if (tbModule) {
        PyRef lines(PyObject_CallMethod(tbModule.get(), "format_exception", "OOO",
            pType.get(), pValue ? pValue.get() : Py_None, pTraceback ? pTraceback.get() : Py_None));
        if (lines) {
            PyRef sep(PyUnicode_FromString(""));
            PyRef joined(sep ? PyUnicode_Join(sep.get(), lines.get()) : nullptr);
            if (joined) result = toUtf8(joined.get());
        }
    }
    if (result.empty()) {
        PyRef repr(PyObject_Repr(pValue ? pValue.get() : pType.get()));
        result = toUtf8(repr.get());
        if (result.empty()) result = "unknown error";
    }
    PyErr_Clear(); // in case formatting itself raised
    return result;
}


// Reads `obj.name` as a bool. Returns `fallback` when the attribute is absent.
// Returns -1 (Python error set) on failure.
int readBoolAttr(PyObject* obj, const char* name, bool fallback)
{
    if (!PyObject_HasAttrString(obj, name)) return fallback ? 1 : 0;
    PyRef attr(PyObject_GetAttrString(obj, name));
    if (!attr) return -1;
    return PyObject_IsTrue(attr.get());
}

} // namespace

PySlaveInstance::PySlaveInstance(std::string instanceName, std::string resources, const cppfmu::Logger& logger, const bool visible, std::shared_ptr<IPyState> pyState)
    : pyState_{ std::move(pyState) }
    , visible_(visible)
    , instanceName_(std::move(instanceName))
    , resources_(std::move(resources))
    , logger_(logger)
{
    py_safe_run([this]() {
        // The destructor does not run when a constructor throws, so release what was
        // acquired so far before propagating the error.
        try {
            // Prepend resources path to python sys path
            PyRef sysModule(PyImport_ImportModule("sys"));
            if (!sysModule) handle_py_exception("[ctor] PyImport_ImportModule(sys)");
            PyRef sysPath(PyObject_GetAttrString(sysModule.get(), "path"));
            if (!sysPath) handle_py_exception("[ctor] PyObject_GetAttrString(sys.path)");
            PyRef resourcesStr(PyUnicode_FromString(resources_.c_str()));
            if (!resourcesStr || PyList_Insert(sysPath.get(), 0, resourcesStr.get()) != 0) {
                handle_py_exception("[ctor] PyList_Insert");
            }

            const auto info = readSlaveModuleInfo(resources_ + "/slavemodule.txt");
            const std::string& moduleName = info.first;
            PyRef module(PyImport_ImportModule(moduleName.c_str()));
            if (!module) handle_py_exception("[ctor] PyImport_ImportModule(" + moduleName + ")");

            std::string className = info.second;
            if (className.empty()) {
                className = findClassName(resources_ + "/" + moduleName + ".py");
            }
            if (className.empty()) {
                throw cppfmu::FatalError("Unable to find class extending Fmi3SlaveBase!");
            }

            pClass_ = PyObject_GetAttrString(module.get(), className.c_str());
            if (pClass_ == nullptr) handle_py_exception("[ctor] PyObject_GetAttr(" + className + ")");

            initialize();
        } catch (...) {
            cleanPyObject();
            throw;
        }
    });
}

void PySlaveInstance::clearLogBuffer() const
{
    clearLogStrBuffer();

    if (pMessages_ == nullptr || !PyList_Check(pMessages_)) {
        return;
    }

    // Logging must never mask the original problem: keep any pending exception aside.
    PyObject *errType, *errValue, *errTraceback;
    PyErr_Fetch(&errType, &errValue, &errTraceback);

    auto& logger = const_cast<cppfmu::Logger&>(logger_);
    const auto size = PyList_Size(pMessages_);
    for (Py_ssize_t i = 0; i < size; i++) {
        PyObject* msg = PyList_GetItem(pMessages_, i); // borrowed

        PyRef debugAttr(PyObject_GetAttrString(msg, "debug"));
        PyRef msgAttr(PyObject_GetAttrString(msg, "msg"));
        PyRef categoryAttr(PyObject_GetAttrString(msg, "category"));
        PyRef statusAttr(PyObject_GetAttrString(msg, "status"));
        if (!debugAttr || !msgAttr || !categoryAttr || !statusAttr) {
            PyErr_Clear();
            continue;
        }

        auto statusValue = static_cast<cppfmu::FMIStatus>(PyLong_AsLong(statusAttr.get()));

        PyObject* msgValue = PyUnicode_AsEncodedString(msgAttr.get(), "utf-8", "replace");
        if (msgValue == nullptr) {
            PyErr_Clear();
            continue;
        }
        const char* msgStr = PyBytes_AsString(msgValue);
        logStrBuffer.emplace_back(msgValue);

        const char* categoryStr = "";
        if (categoryAttr.get() != Py_None) {
            PyObject* categoryValue = PyUnicode_AsEncodedString(categoryAttr.get(), "utf-8", "replace");
            if (categoryValue != nullptr) {
                categoryStr = PyBytes_AsString(categoryValue);
                logStrBuffer.emplace_back(categoryValue);
            }
        }

        if (PyObject_IsTrue(debugAttr.get()) == 1) {
            logger.DebugLog(statusValue, categoryStr, msgStr);
        } else {
            logger.Log(statusValue, categoryStr, msgStr);
        }
        PyErr_Clear();
    }
    PyList_SetSlice(pMessages_, 0, size, nullptr);

    PyErr_Restore(errType, errValue, errTraceback);
}

void PySlaveInstance::initialize()
{
    clearLogBuffer();
    Py_CLEAR(pInstance_);
    Py_CLEAR(pMessages_);

    PyRef args(PyTuple_New(0));
    PyRef kwargs(Py_BuildValue("{ss,ss,sn,si}",
        "instance_name", instanceName_.c_str(),
        "resources", resources_.c_str(),
        "logger", reinterpret_cast<Py_ssize_t>(&logger_),
        "visible", static_cast<int>(visible_)));
    if (!args || !kwargs) handle_py_exception("[initialize] Py_BuildValue");

    pInstance_ = PyObject_Call(pClass_, args.get(), kwargs.get());
    if (pInstance_ == nullptr) handle_py_exception("[initialize] PyObject_Call");

    pMessages_ = PyObject_CallMethod(pInstance_, "_get_log_queue", nullptr);
    if (pMessages_ == nullptr) handle_py_exception("[initialize] _get_log_queue");
    clearLogBuffer();
}

void PySlaveInstance::callVoidMethod(const char* method) const
{
    PyRef result(PyObject_CallMethod(pInstance_, method, nullptr));
    if (!result) handle_py_exception(std::string("[") + method + "]");
    clearLogBuffer();
}

void PySlaveInstance::callSetter(const char* method, const cppfmu::FMIValueReference* vr, std::size_t nvr, PyObject* valuesList)
{
    PyRef values(valuesList);
    if (!values) handle_py_exception(std::string("[") + method + "] building values");
    PyRef vrs(makeVrList(vr, nvr));
    if (!vrs) handle_py_exception(std::string("[") + method + "] building value references");

    PyRef result(PyObject_CallMethod(pInstance_, method, "(OO)", vrs.get(), values.get()));
    if (!result) handle_py_exception(std::string("[") + method + "]");
    clearLogBuffer();
}

PyObject* PySlaveInstance::callGetter(const char* method, const cppfmu::FMIValueReference* vr, std::size_t nvr, std::size_t nValues) const
{
    PyRef vrs(makeVrList(vr, nvr));
    if (!vrs) handle_py_exception(std::string("[") + method + "] building value references");

    PyRef refs(PyObject_CallMethod(pInstance_, method, "(O)", vrs.get()));
    if (!refs) handle_py_exception(std::string("[") + method + "]");
    checkListSize(refs.get(), nValues, method);
    return refs.release();
}

PyObject* PySlaveInstance::callListMethod(const char* method, std::size_t expected) const
{
    PyRef refs(PyObject_CallMethod(pInstance_, method, nullptr));
    if (!refs) handle_py_exception(std::string("[") + method + "]");
    checkListSize(refs.get(), expected, method);
    return refs.release();
}

void PySlaveInstance::checkListSize(PyObject* list, std::size_t expected, const char* method) const
{
    if (!PyList_Check(list)) {
        clearLogBuffer();
        throw std::runtime_error(std::string("[") + method + "] must return a list");
    }
    const auto actual = static_cast<std::size_t>(PyList_Size(list));
    if (actual < expected) {
        clearLogBuffer();
        std::ostringstream oss;
        oss << "[" << method << "] returned " << actual << " values, but " << expected << " were requested";
        throw std::runtime_error(oss.str());
    }
}

void PySlaveInstance::SetupExperiment(cppfmu::FMIBoolean, cppfmu::FMIFloat64, cppfmu::FMIFloat64 startTime, cppfmu::FMIBoolean, cppfmu::FMIFloat64)
{
    py_safe_run([this, startTime]() {
        PyRef result(PyObject_CallMethod(pInstance_, "setup_experiment", "(d)", startTime));
        if (!result) handle_py_exception("[setup_experiment]");
        clearLogBuffer();
    });
}

void PySlaveInstance::EnterInitializationMode()
{
    py_safe_run([this]() { callVoidMethod("enter_initialization_mode"); });
}

void PySlaveInstance::ExitInitializationMode()
{
    py_safe_run([this]() { callVoidMethod("exit_initialization_mode"); });
}

cppfmu::FMIStatus PySlaveInstance::DoStep(cppfmu::FMIFloat64 currentTime,
    cppfmu::FMIFloat64 stepSize,
    cppfmu::FMIBoolean,
    cppfmu::FMIBoolean* eventHandlingNeeded,
    cppfmu::FMIBoolean* terminateSimulation,
    cppfmu::FMIBoolean* earlyReturn,
    cppfmu::FMIFloat64& endOfStep)
{
    // The FMI standard requires these outputs to always be written.
    if (eventHandlingNeeded) *eventHandlingNeeded = false;
    if (terminateSimulation) *terminateSimulation = false;
    if (earlyReturn) *earlyReturn = false;

    return py_safe_run([&]() {
        cppfmu::FMIStatus fmuStatus = cppfmu::FMIOK;
        PyRef result(PyObject_CallMethod(pInstance_, "do_step", "(dd)", currentTime, stepSize));
        if (!result) handle_py_exception("[do_step]");
        PyObject* f = result.get();

        if (PyObject_HasAttrString(f, "status")) {
            PyRef pyStatus(PyObject_GetAttrString(f, "status"));
            if (!pyStatus) handle_py_exception("[do_step] status");
            fmuStatus = static_cast<cppfmu::FMIStatus>(PyLong_AsLong(pyStatus.get()));
            if (PyErr_Occurred()) handle_py_exception("[do_step] status conversion");
        } else {
            const int ok = PyObject_IsTrue(f);
            if (ok < 0) handle_py_exception("[do_step] return value");
            if (!ok) fmuStatus = cppfmu::FMIDiscard;
        }

        const int ehn = readBoolAttr(f, "eventHandlingNeeded", false);
        const int term = readBoolAttr(f, "terminateSimulation", false);
        const int early = readBoolAttr(f, "earlyReturn", false);
        if (ehn < 0 || term < 0 || early < 0) handle_py_exception("[do_step] result");

        if (eventHandlingNeeded) *eventHandlingNeeded = ehn == 1;
        if (terminateSimulation) *terminateSimulation = term == 1;
        if (earlyReturn) *earlyReturn = early == 1;
        if (fmuStatus == cppfmu::FMIOK) endOfStep = currentTime + stepSize;

        clearLogBuffer();
        return fmuStatus;
    });
}

void PySlaveInstance::Reset()
{
    py_safe_run([this]() { initialize(); });
}

void PySlaveInstance::Terminate()
{
    py_safe_run([this]() { callVoidMethod("terminate"); });
}

void PySlaveInstance::SetFloat64(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIFloat64* values, std::size_t nValues)
{
    py_safe_run([&]() {
        callSetter("set_float64", vr, nvr, makeValueList(values, nValues, [](cppfmu::FMIFloat64 v) { return PyFloat_FromDouble(v); }));
    });
}

void PySlaveInstance::SetInt32(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIInt32* values, std::size_t nValues)
{
    py_safe_run([&]() {
        callSetter("set_int32", vr, nvr, makeValueList(values, nValues, [](cppfmu::FMIInt32 v) { return PyLong_FromLong(v); }));
    });
}

void PySlaveInstance::SetInt64(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIInt64* values, std::size_t nValues)
{
    py_safe_run([&]() {
        callSetter("set_int64", vr, nvr, makeValueList(values, nValues, [](cppfmu::FMIInt64 v) { return PyLong_FromLongLong(v); }));
    });
}

void PySlaveInstance::SetUInt64(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIUInt64* values, std::size_t nValues)
{
    py_safe_run([&]() {
        callSetter("set_uint64", vr, nvr, makeValueList(values, nValues, [](cppfmu::FMIUInt64 v) { return PyLong_FromUnsignedLongLong(v); }));
    });
}

void PySlaveInstance::SetBoolean(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIBoolean* values, std::size_t nValues)
{
    py_safe_run([&]() {
        callSetter("set_boolean", vr, nvr, makeValueList(values, nValues, [](cppfmu::FMIBoolean v) { return PyBool_FromLong(v ? 1 : 0); }));
    });
}

void PySlaveInstance::SetString(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIString const* values, std::size_t nValues)
{
    py_safe_run([&]() {
        callSetter("set_string", vr, nvr, makeValueList(values, nValues, makeString));
    });
}

void PySlaveInstance::GetFloat64(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIFloat64* values, std::size_t nValues) const
{
    py_safe_run([&]() {
        PyRef refs(callGetter("get_float64", vr, nvr, nValues));
        for (std::size_t i = 0; i < nValues; i++) {
            values[i] = PyFloat_AsDouble(PyList_GetItem(refs.get(), i));
        }
        if (PyErr_Occurred()) handle_py_exception("[get_float64] conversion");
        clearLogBuffer();
    });
}

void PySlaveInstance::GetInt32(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIInt32* values, std::size_t nValues) const
{
    py_safe_run([&]() {
        PyRef refs(callGetter("get_int32", vr, nvr, nValues));
        for (std::size_t i = 0; i < nValues; i++) {
            values[i] = static_cast<cppfmu::FMIInt32>(PyLong_AsLong(PyList_GetItem(refs.get(), i)));
        }
        if (PyErr_Occurred()) handle_py_exception("[get_int32] conversion");
        clearLogBuffer();
    });
}

void PySlaveInstance::GetInt64(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIInt64* values, std::size_t nValues) const
{
    py_safe_run([&]() {
        PyRef refs(callGetter("get_int64", vr, nvr, nValues));
        for (std::size_t i = 0; i < nValues; i++) {
            values[i] = static_cast<cppfmu::FMIInt64>(PyLong_AsLongLong(PyList_GetItem(refs.get(), i)));
        }
        if (PyErr_Occurred()) handle_py_exception("[get_int64] conversion");
        clearLogBuffer();
    });
}

void PySlaveInstance::GetUInt64(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIUInt64* values, std::size_t nValues) const
{
    py_safe_run([&]() {
        PyRef refs(callGetter("get_uint64", vr, nvr, nValues));
        for (std::size_t i = 0; i < nValues; i++) {
            PyObject* item = PyList_GetItem(refs.get(), i);
            if (PyLong_Check(item)) {
                values[i] = static_cast<cppfmu::FMIUInt64>(PyLong_AsUnsignedLongLong(item));
            } else {
                // ctypes.c_uint64 (as returned by Fmi3SlaveBase.get_uint64)
                PyRef value(PyObject_GetAttrString(item, "value"));
                if (!value) handle_py_exception("[get_uint64] value attribute");
                values[i] = static_cast<cppfmu::FMIUInt64>(PyLong_AsUnsignedLongLong(value.get()));
            }
        }
        if (PyErr_Occurred()) handle_py_exception("[get_uint64] conversion");
        clearLogBuffer();
    });
}

void PySlaveInstance::GetBoolean(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIBoolean* values, std::size_t nValues) const
{
    py_safe_run([&]() {
        PyRef refs(callGetter("get_boolean", vr, nvr, nValues));
        for (std::size_t i = 0; i < nValues; i++) {
            const int v = PyObject_IsTrue(PyList_GetItem(refs.get(), i));
            if (v < 0) handle_py_exception("[get_boolean] conversion");
            values[i] = v == 1;
        }
        clearLogBuffer();
    });
}

void PySlaveInstance::GetString(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIString* values, std::size_t nValues) const
{
    py_safe_run([&]() {
        // Strings returned to the importer stay valid until the next GetString call.
        clearStrBuffer();
        PyRef refs(callGetter("get_string", vr, nvr, nValues));
        for (std::size_t i = 0; i < nValues; i++) {
            PyObject* value = PyUnicode_AsEncodedString(PyList_GetItem(refs.get(), i), "utf-8", nullptr);
            if (value == nullptr) handle_py_exception("[get_string] conversion");
            values[i] = PyBytes_AsString(value);
            strBuffer.emplace_back(value);
        }
        clearLogBuffer();
    });
}

void PySlaveInstance::GetContinuousStates(cppfmu::FMIFloat64* continuousStates, std::size_t nStates) const
{
    py_safe_run([&]() {
        PyRef refs(callListMethod("get_continuous_states", nStates));
        for (std::size_t i = 0; i < nStates; i++) {
            continuousStates[i] = PyFloat_AsDouble(PyList_GetItem(refs.get(), i));
        }
        if (PyErr_Occurred()) handle_py_exception("[get_continuous_states] conversion");
        clearLogBuffer();
    });
}

void PySlaveInstance::GetContinuousStateDerivatives(cppfmu::FMIFloat64* continuousStateDerivatives, std::size_t nStates) const
{
    py_safe_run([&]() {
        PyRef refs(callListMethod("get_continuous_state_derivatives", nStates));
        for (std::size_t i = 0; i < nStates; i++) {
            continuousStateDerivatives[i] = PyFloat_AsDouble(PyList_GetItem(refs.get(), i));
        }
        if (PyErr_Occurred()) handle_py_exception("[get_continuous_state_derivatives] conversion");
        clearLogBuffer();
    });
}

void PySlaveInstance::GetNominalsOfContinuousStates(cppfmu::FMIFloat64* nominalsOfContinuousStates, std::size_t nStates) const
{
    py_safe_run([&]() {
        PyRef refs(PyObject_CallMethod(pInstance_, "get_nominals_of_continuous_states", "(n)", static_cast<Py_ssize_t>(nStates)));
        if (!refs) handle_py_exception("[get_nominals_of_continuous_states]");
        checkListSize(refs.get(), nStates, "get_nominals_of_continuous_states");
        for (std::size_t i = 0; i < nStates; i++) {
            nominalsOfContinuousStates[i] = PyFloat_AsDouble(PyList_GetItem(refs.get(), i));
        }
        if (PyErr_Occurred()) handle_py_exception("[get_nominals_of_continuous_states] conversion");
        clearLogBuffer();
    });
}

void PySlaveInstance::SetContinuousStates(const cppfmu::FMIFloat64* continuousStates, std::size_t nStates)
{
    py_safe_run([&]() {
        PyRef refs(makeValueList(continuousStates, nStates, [](cppfmu::FMIFloat64 v) { return PyFloat_FromDouble(v); }));
        if (!refs) handle_py_exception("[set_continuous_states] building values");
        PyRef result(PyObject_CallMethod(pInstance_, "set_continuous_states", "(O)", refs.get()));
        if (!result) handle_py_exception("[set_continuous_states]");
        clearLogBuffer();
    });
}

void PySlaveInstance::GetNumberOfContinuousStates(std::size_t& nStates) const
{
    py_safe_run([&]() {
        PyRef result(PyObject_CallMethod(pInstance_, "get_number_of_continuous_states", nullptr));
        if (!result) handle_py_exception("[get_number_of_continuous_states]");
        nStates = PyLong_AsSize_t(result.get());
        if (PyErr_Occurred()) handle_py_exception("[get_number_of_continuous_states] conversion");
        clearLogBuffer();
    });
}

void PySlaveInstance::GetNumberOfEventIndicators(std::size_t& nIndicators) const
{
    py_safe_run([&]() {
        PyRef result(PyObject_CallMethod(pInstance_, "get_number_of_event_indicators", nullptr));
        if (!result) handle_py_exception("[get_number_of_event_indicators]");
        nIndicators = PyLong_AsSize_t(result.get());
        if (PyErr_Occurred()) handle_py_exception("[get_number_of_event_indicators] conversion");
        clearLogBuffer();
    });
}

void PySlaveInstance::GetEventIndicators(cppfmu::FMIFloat64* eventIndicators, std::size_t nIndicators) const
{
    py_safe_run([&]() {
        PyRef refs(callListMethod("get_event_indicators", nIndicators));
        for (std::size_t i = 0; i < nIndicators; i++) {
            eventIndicators[i] = PyFloat_AsDouble(PyList_GetItem(refs.get(), i));
        }
        if (PyErr_Occurred()) handle_py_exception("[get_event_indicators] conversion");
        clearLogBuffer();
    });
}

void PySlaveInstance::SetTime(cppfmu::FMIFloat64 time)
{
    py_safe_run([this, time]() {
        PyRef result(PyObject_CallMethod(pInstance_, "set_time", "(d)", time));
        if (!result) handle_py_exception("[set_time]");
        clearLogBuffer();
    });
}

void PySlaveInstance::UpdateDiscreteStates(
    cppfmu::FMIBoolean* discreteStatesNeedUpdate,
    cppfmu::FMIBoolean* terminateSimulation,
    cppfmu::FMIBoolean* nominalContinuousStatesChanged,
    cppfmu::FMIBoolean* valuesOfContinuousStatesChanged,
    cppfmu::FMIBoolean* nextEventTimeDefined,
    cppfmu::FMIFloat64* nextEventTime)
{
    py_safe_run([&]() {
        PyRef result(PyObject_CallMethod(pInstance_, "update_discrete_states", nullptr));
        if (!result) handle_py_exception("[update_discrete_states]");
        PyObject* f = result.get();

        struct Field
        {
            const char* name;
            cppfmu::FMIBoolean* out;
        };
        const Field fields[] = {
            {"discreteStatesNeedUpdate", discreteStatesNeedUpdate},
            {"terminateSimulation", terminateSimulation},
            {"nominalContinuousStatesChanged", nominalContinuousStatesChanged},
            {"valuesOfContinuousStatesChanged", valuesOfContinuousStatesChanged},
            {"nextEventTimeDefined", nextEventTimeDefined},
        };
        for (const auto& field : fields) {
            const int v = readBoolAttr(f, field.name, false);
            if (v < 0) handle_py_exception(std::string("[update_discrete_states] ") + field.name);
            if (field.out) *field.out = v == 1;
        }

        if (nextEventTimeDefined && *nextEventTimeDefined && nextEventTime) {
            PyRef pyNextEventTime(PyObject_GetAttrString(f, "nextEventTime"));
            if (!pyNextEventTime) handle_py_exception("[update_discrete_states] nextEventTime");
            *nextEventTime = PyFloat_AsDouble(pyNextEventTime.get());
            if (PyErr_Occurred()) handle_py_exception("[update_discrete_states] nextEventTime conversion");
        }
        clearLogBuffer();
    });
}

void PySlaveInstance::GetFMUstate(fmi3FMUState& state)
{
    py_safe_run([&]() {
        PyRef newState(PyObject_CallMethod(pInstance_, "_get_fmu_state", nullptr));
        if (!newState) handle_py_exception("[_get_fmu_state]");
        // FMI 3.0: a non-NULL state was returned by an earlier call and must be overwritten.
        PyObject* previous = reinterpret_cast<PyObject*>(state);
        state = reinterpret_cast<fmi3FMUState>(newState.release());
        Py_XDECREF(previous);
        clearLogBuffer();
    });
}

void PySlaveInstance::SetFMUstate(const fmi3FMUState& state)
{
    py_safe_run([&]() {
        auto pyState = reinterpret_cast<PyObject*>(state);
        PyRef result(PyObject_CallMethod(pInstance_, "_set_fmu_state", "(O)", pyState));
        if (!result) handle_py_exception("[_set_fmu_state]");
        clearLogBuffer();
    });
}

void PySlaveInstance::FreeFMUstate(fmi3FMUState& state)
{
    py_safe_run([&]() {
        Py_XDECREF(reinterpret_cast<PyObject*>(state));
        state = nullptr;
    });
}

size_t PySlaveInstance::SerializedFMUstateSize(const fmi3FMUState& state)
{
    return py_safe_run([&]() {
        auto pyState = reinterpret_cast<PyObject*>(state);
        PyRef bytes(PyObject_CallMethod(pClass_, "_fmu_state_to_bytes", "(O)", pyState));
        if (!bytes) handle_py_exception("[_fmu_state_to_bytes]");
        const Py_ssize_t size = PyBytes_Size(bytes.get());
        if (size < 0) handle_py_exception("[_fmu_state_to_bytes] must return bytes");
        clearLogBuffer();
        return static_cast<size_t>(size);
    });
}

void PySlaveInstance::SerializeFMUstate(const fmi3FMUState& state, fmi3Byte* bytes, size_t size)
{
    py_safe_run([&]() {
        auto pyState = reinterpret_cast<PyObject*>(state);
        PyRef pyBytes(PyObject_CallMethod(pClass_, "_fmu_state_to_bytes", "(O)", pyState));
        if (!pyBytes) handle_py_exception("[_fmu_state_to_bytes]");
        char* data = nullptr;
        Py_ssize_t length = 0;
        if (PyBytes_AsStringAndSize(pyBytes.get(), &data, &length) != 0) {
            handle_py_exception("[_fmu_state_to_bytes] must return bytes");
        }
        if (static_cast<size_t>(length) > size) {
            throw std::runtime_error("[SerializeFMUstate] buffer is smaller than fmi3SerializedFMUStateSize");
        }
        std::copy(data, data + length, bytes);
        clearLogBuffer();
    });
}

void PySlaveInstance::DeSerializeFMUstate(const fmi3Byte bytes[], size_t size, fmi3FMUState& state)
{
    py_safe_run([&]() {
        PyRef pyBytes(PyBytes_FromStringAndSize(reinterpret_cast<const char*>(bytes), static_cast<Py_ssize_t>(size)));
        if (!pyBytes) handle_py_exception("[DeSerializeFMUstate] PyBytes_FromStringAndSize");
        PyRef pyState(PyObject_CallMethod(pClass_, "_fmu_state_from_bytes", "(O)", pyBytes.get()));
        if (!pyState) handle_py_exception("[_fmu_state_from_bytes]");
        PyObject* previous = reinterpret_cast<PyObject*>(state);
        state = reinterpret_cast<fmi3FMUState>(pyState.release());
        Py_XDECREF(previous);
        clearLogBuffer();
    });
}

void PySlaveInstance::handle_py_exception(const std::string& what) const
{
    // Must be called with the GIL held. The GIL is released by the enclosing GilGuard
    // while the exception unwinds; Python objects stay valid so the instance can still
    // be freed (or reset) safely afterwards.
    std::string details = fetchPythonError();
    clearLogBuffer(); // forward messages logged before the failure

    std::ostringstream oss;
    oss << "Fatal py exception encountered: " << what << "\n" << details;
    throw cppfmu::FatalError(oss.str().c_str());
}

PySlaveInstance::~PySlaveInstance()
{
    py_safe_run([this]() { cleanPyObject(); });
}

} // namespace pythonfmu

namespace {
    // Never destroyed (allocated once, no static destructor). On Linux the library's
    // destructor function (onLibraryUnload, run by _dl_fini) resets the state after the C++
    // static destructors have run at exit: a namespace-scope shared_ptr was destroyed by then,
    // and resetting it again decremented a reference count in freed memory, corrupting the
    // heap (glibc then aborted in a later free, e.g. libgfortran's close_units).
    std::mutex& pyStateMutex()
    {
        static auto* const mutex = new std::mutex();
        return *mutex;
    }

    std::shared_ptr<pythonfmu::PyState>& pyState()
    {
        static auto* const state = new std::shared_ptr<pythonfmu::PyState>();
        return *state;
    }

    // Turns an FMI 3 resource path (or a legacy file:// URI) into a filesystem path.
    std::string resourcePathFromLocation(const std::string& location)
    {
        std::string path = location;
        const std::string scheme = "file://";
        if (path.compare(0, scheme.size(), scheme) == 0) {
            path.erase(0, scheme.size());
            // file:///C:/... on Windows -> C:/...
            if (path.size() > 2 && path[0] == '/' && path[2] == ':') path.erase(0, 1);

            // Percent-decode (URIs only; plain FMI 3 paths may legitimately contain '%')
            std::string decoded;
            decoded.reserve(path.size());
            for (std::size_t i = 0; i < path.size(); i++) {
                if (path[i] == '%' && i + 2 < path.size() && std::isxdigit(static_cast<unsigned char>(path[i + 1])) &&
                    std::isxdigit(static_cast<unsigned char>(path[i + 2]))) {
                    decoded += static_cast<char>(std::stoi(path.substr(i + 1, 2), nullptr, 16));
                    i += 2;
                } else {
                    decoded += path[i];
                }
            }
            path = decoded;
        }
        while (path.size() > 1 && (path.back() == '/' || path.back() == '\\')) path.pop_back();
        return path;
    }
}

std::unique_ptr<cppfmu::SlaveInstance> CppfmuInstantiateSlave(
    cppfmu::FMIString instanceName,
    cppfmu::FMIString,
    cppfmu::FMIString fmuResourceLocation,
    cppfmu::FMIString,
    cppfmu::FMIFloat64,
    cppfmu::FMIBoolean visible,
    cppfmu::FMIBoolean,
    const cppfmu::Logger& logger)
{
    if (fmuResourceLocation == nullptr) {
        throw cppfmu::FatalError("No resource path given: PythonFMU3 needs the FMU resources folder");
    }
    auto resources = resourcePathFromLocation(fmuResourceLocation);

    auto const ensurePyStateAlive = [&]() {
        auto const lock = std::lock_guard{pyStateMutex()};
        if (nullptr == pyState()) pyState() = std::make_shared<pythonfmu::PyState>();
        return pyState();
    };

    return std::make_unique<pythonfmu::PySlaveInstance>(
        instanceName, resources, logger, visible, ensurePyStateAlive());
}

extern "C" {

    // The PyState instance owns it's own thread for constructing and destroying the Py* from the same thread.
    // Creation of an std::thread increments ref counter of a shared library. So, when the client unloads the library
    // the library won't be freed, as std::thread is alive, and the std::thread itself waits for de-initialization request.
    // Thus, use DllMain on Windows and __attribute__((destructor)) on Linux for signaling to the PyState about de-initialization.
    void finalizePythonInterpreter()
    {
        auto const lock = std::lock_guard{pyStateMutex()};
        pyState().reset();
    }
}

namespace
{
#ifdef _WIN32
#include <windows.h>

    BOOL APIENTRY DllMain(HMODULE hModule,
        DWORD ul_reason_for_call,
        LPVOID lpReserved)
    {
        switch (ul_reason_for_call) {
            case DLL_PROCESS_ATTACH:
                break;
            case DLL_THREAD_ATTACH:
            case DLL_THREAD_DETACH:
                break;
            case DLL_PROCESS_DETACH:
                finalizePythonInterpreter();
                break;
        }
        return TRUE;
}
#elif defined(__linux__) || defined(__APPLE__)
    __attribute__((destructor)) void onLibraryUnload()
    {
        finalizePythonInterpreter();
}
#else
#error port the code
#endif
}
