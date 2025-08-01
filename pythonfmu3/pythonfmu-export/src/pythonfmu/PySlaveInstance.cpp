
#include "pythonfmu/IPyState.hpp"
#include "pythonfmu/PySlaveInstance.hpp"

#include "pythonfmu/PyState.hpp"

#include "cppfmu/cppfmu_cs.hpp"

#include <fstream>
#include <functional>
#include <mutex>
#include <regex>
#include <sstream>
#include <utility>

namespace pythonfmu
{

inline std::string getline(const std::string& fileName)
{
    std::string line;
    std::ifstream infile(fileName);
    std::getline(infile, line);
    return line;
}

inline std::string findClassName(const std::string& fileName)
{
    std::string line;
    std::ifstream infile(fileName);
    std::string regexStr(R"(^class (\w+)\(([^)]*\bFmi3Slave(?:Base)?\b[^)]*)\)\s*:)");
    while (getline(infile, line)) {
        std::smatch m;
        std::regex re(regexStr);
        if (std::regex_search(line, m, re)) {
            return m[1];
        }
    }
    return "";
}

inline void py_safe_run(const std::function<void(PyGILState_STATE gilState)>& f)
{
    PyGILState_STATE gil_state = PyGILState_Ensure();
    f(gil_state);
    PyGILState_Release(gil_state);
}

PySlaveInstance::PySlaveInstance(std::string instanceName, std::string resources, const cppfmu::Logger& logger, const bool visible, std::shared_ptr<IPyState> pyState)
    : pyState_{ std::move(pyState) }
    , instanceName_(std::move(instanceName))
    , resources_(std::move(resources))
    , logger_(logger)
    , visible_(visible)
{
    py_safe_run([this](PyGILState_STATE gilState) {
        // Append resources path to python sys path
        PyObject* sys_module = PyImport_ImportModule("sys");
        if (sys_module == nullptr) {
            handle_py_exception("[ctor] PyImport_ImportModule", gilState);
        }
        PyObject* sys_path = PyObject_GetAttrString(sys_module, "path");
        Py_DECREF(sys_module);
        if (sys_path == nullptr) {
            handle_py_exception("[ctor] PyObject_GetAttrString", gilState);
        }
        int success = PyList_Insert(sys_path, 0, PyUnicode_FromString(resources_.c_str()));
        Py_DECREF(sys_path);
        if (success != 0) {
            handle_py_exception("[ctor] PyList_Insert", gilState);
        }

        std::string moduleName = getline(resources_ + "/slavemodule.txt");
        PyObject* pModule = PyImport_ImportModule(moduleName.c_str());
        if (pModule == nullptr) {
            PyErr_Print();
            handle_py_exception("[ctor] PyImport_ImportModule", gilState);
        }

        std::string className = findClassName(resources_ + "/" + moduleName + ".py");
        if (className.empty()) {
            cleanPyObject();
            throw cppfmu::FatalError("Unable to find class extending Fmi3SlaveBase!");
        }

        PyObject* pyClassName = Py_BuildValue("s", className.c_str());
        if (pyClassName == nullptr) {
            handle_py_exception("[ctor] Py_BuildValue", gilState);
        }

        pClass_ = PyObject_GetAttr(pModule, pyClassName);
        Py_DECREF(pyClassName);
        Py_DECREF(pModule);
        if (pClass_ == nullptr) {
            handle_py_exception("[ctor] PyObject_GetAttr", gilState);
        }

        initialize(gilState);
    });
}

void PySlaveInstance::clearLogBuffer() const
{
    clearLogStrBuffer();

    PyObject* debugField = Py_BuildValue("s", "debug");
    PyObject* msgField = Py_BuildValue("s", "msg");
    PyObject* categoryField = Py_BuildValue("s", "category");
    PyObject* statusField = Py_BuildValue("s", "status");

    if ( pMessages_ != NULL && PyList_Check(pMessages_) ) {
        auto size = PyList_Size(pMessages_);
        for (auto i = 0; i < size; i++) {
            PyObject* msg = PyList_GetItem(pMessages_, i);

            auto debugAttr = PyObject_GetAttr(msg, debugField);
            auto msgAttr = PyObject_GetAttr(msg, msgField);
            auto categoryAttr = PyObject_GetAttr(msg, categoryField);
            auto statusAttr = PyObject_GetAttr(msg, statusField);

            auto statusValue = static_cast<cppfmu::FMIStatus>(PyLong_AsLong(statusAttr));

            PyObject* msgValue = PyUnicode_AsEncodedString(msgAttr, "utf-8", nullptr);
            char* msgStr = PyBytes_AsString(msgValue);
            logStrBuffer.emplace_back(msgValue);

            const char* categoryStr = "";
            if (categoryAttr != Py_None) {
                PyObject* categoryValue = PyUnicode_AsEncodedString(categoryAttr, "utf-8", nullptr);
                categoryStr = PyBytes_AsString(categoryValue);
                logStrBuffer.emplace_back(categoryValue);
            }

            if (PyObject_IsTrue(debugAttr)) {
                const_cast<cppfmu::Logger&>(logger_).DebugLog(statusValue, categoryStr, msgStr);
            } else {
                const_cast<cppfmu::Logger&>(logger_).Log(statusValue, categoryStr, msgStr);
            }
        }
        PyList_SetSlice(pMessages_, 0, size, nullptr);
    }
    Py_DECREF(debugField);
    Py_DECREF(msgField);
    Py_DECREF(categoryField);
    Py_DECREF(statusField);
}

void PySlaveInstance::initialize(PyGILState_STATE gilState)
{
    Py_XDECREF(pInstance_);
    Py_XDECREF(pMessages_);

    PyObject* args = PyTuple_New(0);
    PyObject* kwargs = Py_BuildValue("{ss,ss,sn,si}",
        "instance_name", instanceName_.c_str(),
        "resources", resources_.c_str(),
        "logger", &logger_,
        "visible", visible_);
    pInstance_ = PyObject_Call(pClass_, args, kwargs);
    Py_DECREF(args);
    Py_DECREF(kwargs);
    if (pInstance_ == nullptr) {
        handle_py_exception("[initialize] PyObject_Call", gilState);
    }
    pMessages_ = PyObject_CallMethod(pInstance_, "_get_log_queue", nullptr);
}

void PySlaveInstance::SetupExperiment(cppfmu::FMIBoolean, cppfmu::FMIFloat64, cppfmu::FMIFloat64 startTime, cppfmu::FMIBoolean, cppfmu::FMIFloat64)
{
    py_safe_run([this, startTime](PyGILState_STATE gilState) {
        auto f = PyObject_CallMethod(pInstance_, "setup_experiment", "(d)", startTime);
        if (f == nullptr) {
            handle_py_exception("[setupExperiment] PyObject_CallMethod", gilState);
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::EnterInitializationMode()
{
    py_safe_run([this](PyGILState_STATE gilState) {
        auto f = PyObject_CallMethod(pInstance_, "enter_initialization_mode", nullptr);
        if (f == nullptr) {
            handle_py_exception("[enterInitializationMode] PyObject_CallMethod", gilState);
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::ExitInitializationMode()
{
    py_safe_run([this](PyGILState_STATE gilState) {
        auto f = PyObject_CallMethod(pInstance_, "exit_initialization_mode", nullptr);
        if (f == nullptr) {
            handle_py_exception("[exitInitializationMode] PyObject_CallMethod", gilState);
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

cppfmu::FMIStatus PySlaveInstance::DoStep(cppfmu::FMIFloat64 currentTime,
    cppfmu::FMIFloat64 stepSize,
    cppfmu::FMIBoolean noSetFmuStatePriorToCurrentPoint,
    cppfmu::FMIBoolean* eventHandlingNeeded,
    cppfmu::FMIBoolean* terminateSimulation,
    cppfmu::FMIBoolean* earlyReturn,
    cppfmu::FMIFloat64& endOfStep)
{
    cppfmu::FMIStatus fmuStatus = cppfmu::FMIOK;
    py_safe_run([this, &fmuStatus, currentTime, stepSize, terminateSimulation](PyGILState_STATE gilState) {
        auto f = PyObject_CallMethod(pInstance_, "do_step", "(dd)", currentTime, stepSize);
        if (f == nullptr) {
            handle_py_exception("[doStep] PyObject_CallMethod", gilState);
        }

        if (PyObject_HasAttrString(f, "status")) {
            PyObject* pyStatus = PyObject_GetAttrString(f, "status");
            if (pyStatus) {
                fmuStatus = static_cast<cppfmu::FMIStatus>(PyLong_AsLong(pyStatus));
                Py_DECREF(pyStatus);
            }
        } else {
            bool status = static_cast<bool>(PyObject_IsTrue(f));
            if (!status) {
                fmuStatus = cppfmu::FMIDiscard;
            }
        }

        if (PyObject_HasAttrString(f, "terminateSimulation")) {
            PyObject* pyTerminateSimulation = PyObject_GetAttrString(f, "terminateSimulation");
            if (pyTerminateSimulation) {
                *terminateSimulation = static_cast<bool>(PyObject_IsTrue(pyTerminateSimulation));
                Py_DECREF(pyTerminateSimulation);
            }
        }
        Py_DECREF(f);
        clearLogBuffer();
    });

    return fmuStatus;
}

void PySlaveInstance::Reset()
{
    py_safe_run([this](PyGILState_STATE gilState) {
        initialize(gilState);
    });
}

void PySlaveInstance::Terminate()
{
    py_safe_run([this](PyGILState_STATE gilState) {
        auto f = PyObject_CallMethod(pInstance_, "terminate", nullptr);
        if (f == nullptr) {
            handle_py_exception("[terminate] PyObject_CallMethod", gilState);
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::SetFloat64(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIFloat64* values, std::size_t nValues)
{
    py_safe_run([this, &vr, nvr, &values, nValues](PyGILState_STATE gilState) {
        PyObject* vrs = PyList_New(nvr);
        PyObject* refs = PyList_New(nValues);
        for (int i = 0; i < nvr; i++) {
            PyList_SetItem(vrs, i, Py_BuildValue("i", vr[i]));
        }
        for (int i = 0; i < nValues; i++) {
            PyList_SetItem(refs, i, Py_BuildValue("d", values[i]));
        }

        auto f = PyObject_CallMethod(pInstance_, "set_float64", "(OO)", vrs, refs);
        Py_DECREF(vrs);
        Py_DECREF(refs);
        if (f == nullptr) {
            handle_py_exception("[setFloat64] PyObject_CallMethod", gilState);
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::SetInt32(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIInt32* values)
{
    py_safe_run([this, &vr, nvr, &values](PyGILState_STATE gilState) {
        PyObject* vrs = PyList_New(nvr);
        PyObject* refs = PyList_New(nvr);
        for (int i = 0; i < nvr; i++) {
            PyList_SetItem(vrs, i, Py_BuildValue("i", vr[i]));
            PyList_SetItem(refs, i, Py_BuildValue("i", values[i]));
        }

        auto f = PyObject_CallMethod(pInstance_, "set_int32", "(OO)", vrs, refs);
        Py_DECREF(vrs);
        Py_DECREF(refs);
        if (f == nullptr) {
            handle_py_exception("[setInt32] PyObject_CallMethod", gilState);
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::SetInt64(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIInt64* values)
{
    py_safe_run([this, &vr, nvr, &values](PyGILState_STATE gilState) {
        PyObject* vrs = PyList_New(nvr);
        PyObject* refs = PyList_New(nvr);
        for (int i = 0; i < nvr; i++) {
            PyList_SetItem(vrs, i, Py_BuildValue("i", vr[i]));
            PyList_SetItem(refs, i, Py_BuildValue("L", values[i]));
        }

        auto f = PyObject_CallMethod(pInstance_, "set_int64", "(OO)", vrs, refs);
        Py_DECREF(vrs);
        Py_DECREF(refs);
        if (f == nullptr) {
            handle_py_exception("[setInt64] PyObject_CallMethod", gilState);
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::SetUInt64(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIUInt64* values)
{
    py_safe_run([this, &vr, nvr, &values](PyGILState_STATE gilState) {
        PyObject* vrs = PyList_New(nvr);
        PyObject* refs = PyList_New(nvr);
        for (int i = 0; i < nvr; i++) {
            PyList_SetItem(vrs, i, Py_BuildValue("i", vr[i]));
            PyList_SetItem(refs, i, Py_BuildValue("K", values[i]));
        }

        auto f = PyObject_CallMethod(pInstance_, "set_uint64", "(OO)", vrs, refs);
        Py_DECREF(vrs);
        Py_DECREF(refs);
        if (f == nullptr) {
            handle_py_exception("[setUInt64] PyObject_CallMethod", gilState);
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::SetBoolean(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIBoolean* values)
{
    py_safe_run([this, &vr, nvr, &values](PyGILState_STATE gilState) {
        PyObject* vrs = PyList_New(nvr);
        PyObject* refs = PyList_New(nvr);
        for (int i = 0; i < nvr; i++) {
            PyList_SetItem(vrs, i, Py_BuildValue("i", vr[i]));
            PyList_SetItem(refs, i, PyBool_FromLong(values[i]));
        }

        auto f = PyObject_CallMethod(pInstance_, "set_boolean", "(OO)", vrs, refs);
        Py_DECREF(vrs);
        Py_DECREF(refs);
        if (f == nullptr) {
            handle_py_exception("[setBoolean] PyObject_CallMethod", gilState);
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::SetString(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIString const* values)
{
    py_safe_run([this, &vr, nvr, &values](PyGILState_STATE gilState) {
        PyObject* vrs = PyList_New(nvr);
        PyObject* refs = PyList_New(nvr);
        for (int i = 0; i < nvr; i++) {
            PyList_SetItem(vrs, i, Py_BuildValue("i", vr[i]));
            PyList_SetItem(refs, i, Py_BuildValue("s", values[i]));
        }

        auto f = PyObject_CallMethod(pInstance_, "set_string", "(OO)", vrs, refs);
        Py_DECREF(vrs);
        Py_DECREF(refs);
        if (f == nullptr) {
            handle_py_exception("[setString] PyObject_CallMethod", gilState);
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::GetFloat64(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIFloat64* values, std::size_t nValues) const
{
    py_safe_run([this, &vr, nvr, &values, nValues](PyGILState_STATE gilState) {
        PyObject* vrs = PyList_New(nvr);
        for (int i = 0; i < nvr; i++) {
            PyList_SetItem(vrs, i, Py_BuildValue("i", vr[i]));
        }

        auto refs = PyObject_CallMethod(pInstance_, "get_float64", "O", vrs);
        Py_DECREF(vrs);
        if (refs == nullptr) {
            handle_py_exception("[getFloat64] PyObject_CallMethod", gilState);
        }

        for (int i = 0; i < nValues; i++) {
            PyObject* value = PyList_GetItem(refs, i);
            values[i] = PyFloat_AsDouble(value);
        }
        Py_DECREF(refs);
        clearLogBuffer();
    });
}

void PySlaveInstance::GetInt32(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIInt32* values) const
{
    py_safe_run([this, &vr, nvr, &values](PyGILState_STATE gilState) {
        PyObject* vrs = PyList_New(nvr);
        for (int i = 0; i < nvr; i++) {
            PyList_SetItem(vrs, i, Py_BuildValue("i", vr[i]));
        }
        auto refs = PyObject_CallMethod(pInstance_, "get_int32", "O", vrs);
        Py_DECREF(vrs);
        if (refs == nullptr) {
            handle_py_exception("[getInt32] PyObject_CallMethod", gilState);
        }

        for (int i = 0; i < nvr; i++) {
            PyObject* value = PyList_GetItem(refs, i);
            values[i] = static_cast<cppfmu::FMIInt32>(PyLong_AsLong(value));
        }
        Py_DECREF(refs);
        clearLogBuffer();
    });
}

void PySlaveInstance::GetInt64(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIInt64* values) const
{
    py_safe_run([this, &vr, nvr, &values](PyGILState_STATE gilState) {
        PyObject* vrs = PyList_New(nvr);
        for (int i = 0; i < nvr; i++) {
            PyList_SetItem(vrs, i, Py_BuildValue("i", vr[i]));
        }
        auto refs = PyObject_CallMethod(pInstance_, "get_int64", "O", vrs);
        Py_DECREF(vrs);
        if (refs == nullptr) {
            handle_py_exception("[getInt64] PyObject_CallMethod", gilState);
        }

        for (int i = 0; i < nvr; i++) {
            PyObject* value = PyList_GetItem(refs, i);
            values[i] = static_cast<cppfmu::FMIInt64>(PyLong_AsLongLong(value));
        }
        Py_DECREF(refs);
        clearLogBuffer();
    });
}

void PySlaveInstance::GetUInt64(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIUInt64* values) const
{
    py_safe_run([this, &vr, nvr, &values](PyGILState_STATE gilState) {
        PyObject* vrs = PyList_New(nvr);
        for (int i = 0; i < nvr; i++) {
            PyList_SetItem(vrs, i, Py_BuildValue("i", vr[i]));
        }
        auto refs = PyObject_CallMethod(pInstance_, "get_uint64", "O", vrs);
        Py_DECREF(vrs);
        if (refs == nullptr) {
            handle_py_exception("[getUInt64] PyObject_CallMethod", gilState);
        }

        for (int i = 0; i < nvr; i++) {
            PyObject* item = PyList_GetItem(refs, i);
            PyObject* value = PyObject_GetAttrString(item, "value");
            if (value && PyLong_Check(value))
            {
                values[i] = static_cast<cppfmu::FMIUInt64>(PyLong_AsUnsignedLongLong(value));
            }
        }

        Py_DECREF(refs);
        clearLogBuffer();
    });
}

void PySlaveInstance::GetBoolean(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIBoolean* values) const
{
    py_safe_run([this, &vr, nvr, &values](PyGILState_STATE gilState) {
        PyObject* vrs = PyList_New(nvr);
        for (int i = 0; i < nvr; i++) {
            PyList_SetItem(vrs, i, Py_BuildValue("i", vr[i]));
        }
        auto refs = PyObject_CallMethod(pInstance_, "get_boolean", "O", vrs);
        Py_DECREF(vrs);
        if (refs == nullptr) {
            handle_py_exception("[getBoolean] PyObject_CallMethod", gilState);
        }

        for (int i = 0; i < nvr; i++) {
            PyObject* value = PyList_GetItem(refs, i);
            values[i] = PyObject_IsTrue(value);
        }
        Py_DECREF(refs);
        clearLogBuffer();
    });
}

void PySlaveInstance::GetString(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIString* values) const
{
    py_safe_run([this, &vr, nvr, &values](PyGILState_STATE gilState) {
        clearStrBuffer();
        PyObject* vrs = PyList_New(nvr);
        for (int i = 0; i < nvr; i++) {
            PyList_SetItem(vrs, i, Py_BuildValue("i", vr[i]));
        }
        auto refs = PyObject_CallMethod(pInstance_, "get_string", "O", vrs);
        Py_DECREF(vrs);
        if (refs == nullptr) {
            handle_py_exception("[getString] PyObject_CallMethod", gilState);
        }

        for (int i = 0; i < nvr; i++) {
            PyObject* value = PyUnicode_AsEncodedString(PyList_GetItem(refs, i), "utf-8", nullptr);
            values[i] = PyBytes_AsString(value);
            strBuffer.emplace_back(value);
        }
        Py_DECREF(refs);
        clearLogBuffer();
    });
}

void PySlaveInstance::GetContinuousStates(cppfmu::FMIFloat64* continuousStates, std::size_t nStates) const
{
    py_safe_run([this, &continuousStates, nStates](PyGILState_STATE gilState) {
        auto f = PyObject_CallMethod(pInstance_, "get_continuous_states", nullptr);
        if (f == nullptr) {
            handle_py_exception("[get_continuous_states] PyObject_CallMethod", gilState);
        }
        // Assuming f is a list of floats
        for (std::size_t i = 0; i < nStates; i++) {
            PyObject* item = PyList_GetItem(f, i);
            continuousStates[i] = static_cast<cppfmu::FMIFloat64>(PyFloat_AsDouble(item));
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::GetContinuousStateDerivatives(cppfmu::FMIFloat64* continuousStateDerivatives, std::size_t nStates) const
{
    py_safe_run([this, &continuousStateDerivatives, nStates](PyGILState_STATE gilState) {
        auto f = PyObject_CallMethod(pInstance_, "get_continuous_state_derivatives", nullptr);
        if (f == nullptr) {
            PyErr_Print();
            handle_py_exception("[get_continuous_state_derivatives] PyObject_CallMethod", gilState);
        }
        // Assuming f is a list of floats
        for (std::size_t i = 0; i < nStates; i++) {
            PyObject* item = PyList_GetItem(f, i);
            continuousStateDerivatives[i] = static_cast<cppfmu::FMIFloat64>(PyFloat_AsDouble(item));
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::GetNominalsOfContinuousStates(cppfmu::FMIFloat64* nominalsOfContinuousStates, std::size_t nStates) const
{
    py_safe_run([this, &nominalsOfContinuousStates, nStates](PyGILState_STATE gilState) {
        auto f = PyObject_CallMethod(pInstance_, "get_nominals_of_continuous_states", "(i)", static_cast<int>(nStates));
         // Check if f is a valid object
         if (f == nullptr) {
            handle_py_exception("[getNominalContinuousStates] PyObject_CallMethod", gilState);
        }
        // Assuming f is a list of floats
        for (std::size_t i = 0; i < nStates; i++) {
            PyObject* item = PyList_GetItem(f, i);
            nominalsOfContinuousStates[i] = static_cast<cppfmu::FMIFloat64>(PyFloat_AsDouble(item));
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::SetContinuousStates(const cppfmu::FMIFloat64* continuousStates, std::size_t nStates)
{
    py_safe_run([this, &continuousStates, nStates](PyGILState_STATE gilState) {
        PyObject* refs = PyList_New(nStates);
        for (int i = 0; i < nStates; i++) {
            PyList_SetItem(refs, i, Py_BuildValue("d", continuousStates[i]));
        }

        auto f = PyObject_CallMethod(pInstance_, "set_continuous_states", "(O)", refs);
        Py_DECREF(refs);
        if (f == nullptr) {
            handle_py_exception("[setContinuousStates] PyObject_CallMethod", gilState);
        }
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::GetNumberOfContinuousStates(std::size_t& nStates) const
{
    py_safe_run([this, &nStates](PyGILState_STATE gilState) {
        auto f = PyObject_CallMethod(pInstance_, "get_number_of_continuous_states", nullptr);
        if (f == nullptr) {
            handle_py_exception("[getNumberOfContinuousStates] PyObject_CallMethod", gilState);
        }
        nStates = static_cast<std::size_t>(PyLong_AsLong(f));
        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::GetNumberOfEventIndicators(std::size_t& nIndicators) const
{
    py_safe_run([this, &nIndicators](PyGILState_STATE gilState) {
         auto f = PyObject_CallMethod(pInstance_, "get_number_of_event_indicators", nullptr);
         if (f == nullptr) {
             handle_py_exception("[getNumberOfEventIndicators] PyObject_CallMethod", gilState);
         }
         nIndicators = static_cast<std::size_t>(PyLong_AsLong(f));
         Py_DECREF(f);
         clearLogBuffer();
    });
}

void PySlaveInstance::GetEventIndicators(cppfmu::FMIFloat64* eventIndicators, std::size_t nIndicators) const
{
    py_safe_run([this, &eventIndicators, nIndicators](PyGILState_STATE gilState) {
        auto f = PyObject_CallMethod(pInstance_, "get_event_indicators", nullptr);
        if (f == nullptr) {
            handle_py_exception("[getEventIndicators] PyObject_CallMethod", gilState);
        }
        // Assuming f is a list of floats
        for (std::size_t i = 0; i < nIndicators; i++) {
            PyObject* item = PyList_GetItem(f, i);
            eventIndicators[i] = static_cast<cppfmu::FMIFloat64>(PyFloat_AsDouble(item));
        }
        Py_DECREF(f);
        clearLogBuffer();
    });

}


void PySlaveInstance::SetTime(cppfmu::FMIFloat64 time)
{
    py_safe_run([this, time](PyGILState_STATE gilState) {
        auto f = PyObject_CallMethod(pInstance_, "set_time", "(d)", time);
        if (f == nullptr) {
            handle_py_exception("[setTime] PyObject_CallMethod", gilState);
        }
        Py_DECREF(f);
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
    py_safe_run([this, discreteStatesNeedUpdate, terminateSimulation, nominalContinuousStatesChanged, valuesOfContinuousStatesChanged, nextEventTimeDefined, nextEventTime](PyGILState_STATE gilState) {
        auto f = PyObject_CallMethod(pInstance_, "update_discrete_states", nullptr);
        if (f == nullptr) {
            handle_py_exception("[updateDiscreteStates] PyObject_CallMethod", gilState);
        }

        if (PyObject_HasAttrString(f, "discreteStatesNeedUpdate")) {
            PyObject * pyDiscreteStatesNeedUpdate = PyObject_GetAttrString(f, "discreteStatesNeedUpdate");
            *discreteStatesNeedUpdate = static_cast<bool>(PyObject_IsTrue(pyDiscreteStatesNeedUpdate));
            Py_DECREF(pyDiscreteStatesNeedUpdate);
        }
        if (PyObject_HasAttrString(f, "terminateSimulation")) {
            PyObject* pyTerminateSimulation = PyObject_GetAttrString(f, "terminateSimulation");
            *terminateSimulation = static_cast<bool>(PyObject_IsTrue(pyTerminateSimulation));
            Py_DECREF(pyTerminateSimulation);
        }
        if (PyObject_HasAttrString(f, "nominalContinuousStatesChanged")) {
            PyObject* pyNominalContinuousStatesChanged = PyObject_GetAttrString(f, "nominalContinuousStatesChanged");
            *nominalContinuousStatesChanged = static_cast<bool>(PyObject_IsTrue(pyNominalContinuousStatesChanged));
            Py_DECREF(pyNominalContinuousStatesChanged);
        }
        if (PyObject_HasAttrString(f, "valuesOfContinuousStatesChanged")) {
            PyObject* pyValuesOfContinuousStatesChanged = PyObject_GetAttrString(f, "valuesOfContinuousStatesChanged");
            *valuesOfContinuousStatesChanged = static_cast<bool>(PyObject_IsTrue(pyValuesOfContinuousStatesChanged));
            Py_DECREF(pyValuesOfContinuousStatesChanged);
        }
        if (PyObject_HasAttrString(f, "nextEventTimeDefined")) {
            PyObject* pyNextEventTimeDefined = PyObject_GetAttrString(f, "nextEventTimeDefined");
            *nextEventTimeDefined = static_cast<bool>(PyObject_IsTrue(pyNextEventTimeDefined));
            Py_DECREF(pyNextEventTimeDefined);
        }
        if (nextEventTimeDefined && *nextEventTimeDefined) {
            PyObject* pyNextEventTime = PyObject_GetAttrString(f, "nextEventTime");
            *nextEventTime = PyFloat_AsDouble(pyNextEventTime);
            Py_DECREF(pyNextEventTime);
        }

        Py_DECREF(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::GetFMUstate(fmi3FMUState& state)
{
    py_safe_run([this, &state](PyGILState_STATE gilState) {
        auto f = PyObject_CallMethod(pInstance_, "_get_fmu_state", nullptr);
        if (f == nullptr) {
            handle_py_exception("[_get_fmu_state] PyObject_CallMethod", gilState);
        }
        state = reinterpret_cast<fmi3FMUState*>(f);
        clearLogBuffer();
    });
}

void PySlaveInstance::SetFMUstate(const fmi3FMUState& state)
{
    py_safe_run([this, &state](PyGILState_STATE gilState) {
        auto pyState = reinterpret_cast<PyObject*>(state);
        auto f = PyObject_CallMethod(pInstance_, "_set_fmu_state", "(O)", pyState);
        if (f == nullptr) {
            handle_py_exception("[_set_fmu_state] PyObject_CallMethod", gilState);
        }
        clearLogBuffer();
    });
}

void PySlaveInstance::FreeFMUstate(fmi3FMUState& state)
{
    py_safe_run([this, &state](PyGILState_STATE gilState) {
        auto f = reinterpret_cast<PyObject*>(state);
        Py_XDECREF(f);
    });
}

size_t PySlaveInstance::SerializedFMUstateSize(const fmi3FMUState& state)
{
    size_t size;
    py_safe_run([this, &state, &size](PyGILState_STATE gilState) {
        auto pyState = reinterpret_cast<PyObject*>(state);
        PyObject* pyStateBytes = PyObject_CallMethod(pClass_, "_fmu_state_to_bytes", "(O)", pyState);
        if (pyStateBytes == nullptr) {
            handle_py_exception("[SerializedFMUstateSize] PyObject_CallMethod", gilState);
        }
        size = PyBytes_Size(pyStateBytes);
        Py_DECREF(pyStateBytes);
        clearLogBuffer();
    });
    return size;
}

void PySlaveInstance::SerializeFMUstate(const fmi3FMUState& state, fmi3Byte* bytes, size_t size)
{
    py_safe_run([this, &state, &bytes, size](PyGILState_STATE gilState) {
        auto pyState = reinterpret_cast<PyObject*>(state);
        PyObject* pyStateBytes = PyObject_CallMethod(pClass_, "_fmu_state_to_bytes", "(O)", pyState);
        if (pyStateBytes == nullptr) {
            handle_py_exception("[SerializeFMUstate] PyObject_CallMethod", gilState);
        }
        char* c = PyBytes_AsString(pyStateBytes);
        if (c == nullptr) {
            handle_py_exception("[SerializeFMUstate] PyBytes_AsString", gilState);
        }
        for (int i = 0; i < size; i++) {
            bytes[i] = c[i];
        }
        Py_DECREF(pyStateBytes);
        clearLogBuffer();
    });
}

void PySlaveInstance::DeSerializeFMUstate(const fmi3Byte bytes[], size_t size, fmi3FMUState& state)
{
    py_safe_run([this, &bytes, size, &state](PyGILState_STATE gilState) {
        char const * castedBytes = reinterpret_cast<char const*>(bytes);
        PyObject* pyStateBytes = PyBytes_FromStringAndSize(castedBytes, size);
        if (pyStateBytes == nullptr) {
            handle_py_exception("[DeSerializeFMUstate] PyBytes_FromStringAndSize", gilState);
        }
        PyObject* pyState = PyObject_CallMethod(pClass_, "_fmu_state_from_bytes", "(O)", pyStateBytes);
        if (pyState == nullptr) {
            handle_py_exception("[DeSerializeFMUstate] PyObject_CallMethod", gilState);
        }
        state = reinterpret_cast<fmi3FMUState*>(pyState);
        Py_DECREF(pyStateBytes);
        clearLogBuffer();
    });
}

void PySlaveInstance::handle_py_exception(const std::string& what, PyGILState_STATE gilState) const
{
    auto err = PyErr_Occurred();
    if (err != nullptr) {
        cleanPyObject();

        PyObject *pExcType, *pExcValue, *pExcTraceback;
        PyErr_Fetch(&pExcType, &pExcValue, &pExcTraceback);

        std::ostringstream oss;
        oss << "Fatal py exception encountered: ";
        oss << what << "\n";
        if (pExcValue != nullptr) {
            PyObject* pRepr = PyObject_Repr(pExcValue);
            PyObject* pyStr = PyUnicode_AsEncodedString(pRepr, "utf-8", nullptr);
            oss << PyBytes_AsString(pyStr);
            Py_DECREF(pyStr);
            Py_DECREF(pRepr);
        } else {
            oss << "unknown error";
        }

        PyErr_Clear();

        Py_XDECREF(pExcType);
        Py_XDECREF(pExcValue);
        Py_XDECREF(pExcTraceback);

        PyGILState_Release(gilState);

        auto msg = oss.str();
        throw cppfmu::FatalError(msg.c_str());
    }
}

PySlaveInstance::~PySlaveInstance()
{
    py_safe_run([this](PyGILState_STATE gilState) {
        cleanPyObject();
    });
}

} // namespace pythonfmu

namespace {
    std::mutex pyStateMutex{};
    std::shared_ptr<pythonfmu::PyState> pyState{};
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

    // Convert URI %20 to space
    auto resources = std::regex_replace(std::string(fmuResourceLocation), std::regex("%20"), " ");
    auto find = resources.find("file://");

    if (find != std::string::npos) {
#ifdef _MSC_VER
        resources.replace(find, 8, "");
#else
        resources.replace(find, 7, "");
#endif
    }

    {
        auto const ensurePyStateAlive = [&]() {
            auto const lock = std::lock_guard{pyStateMutex};
            if (nullptr == pyState) pyState = std::make_shared<pythonfmu::PyState>();
            };

        ensurePyStateAlive();
        return std::make_unique<pythonfmu::PySlaveInstance>(
            instanceName, resources, logger, visible, pyState);
    }
}

extern "C" {

    // The PyState instance owns it's own thread for constructing and destroying the Py* from the same thread.
    // Creation of an std::thread increments ref counter of a shared library. So, when the client unloads the library
    // the library won't be freed, as std::thread is alive, and the std::thread itself waits for de-initialization request.
    // Thus, use DllMain on Windows and __attribute__((destructor)) on Linux for signaling to the PyState about de-initialization.
    void finalizePythonInterpreter()
    {
        pyState = nullptr;
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
