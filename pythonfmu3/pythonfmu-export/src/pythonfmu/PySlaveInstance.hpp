
#ifndef PYTHONFMU_SLAVEINSTANCE_HPP
#define PYTHONFMU_SLAVEINSTANCE_HPP

#include "cppfmu/cppfmu_cs.hpp"
#include "pythonfmu/IPyState.hpp"

#include <Python.h>
#include <string>
#include <vector>

namespace pythonfmu
{

class PySlaveInstance : public cppfmu::SlaveInstance
{

public:
    PySlaveInstance(std::string instanceName, std::string resources, const cppfmu::Logger& logger, bool visible, std::shared_ptr<IPyState> pyState);

    // Must be called with the GIL held.
    void initialize();

    void SetupExperiment(cppfmu::FMIBoolean toleranceDefined, cppfmu::FMIFloat64 tolerance, cppfmu::FMIFloat64 tStart, cppfmu::FMIBoolean stopTimeDefined, cppfmu::FMIFloat64 tStop) override;
    void EnterInitializationMode() override;
    void ExitInitializationMode() override;
    void Terminate() override;
    void Reset() override;
    cppfmu::FMIStatus DoStep(cppfmu::FMIFloat64 currentCommunicationPoint,
        cppfmu::FMIFloat64 communicationStepSize,
        cppfmu::FMIBoolean newStep,
        cppfmu::FMIBoolean* eventHandlingNeeded,
        cppfmu::FMIBoolean* terminateSimulation,
        cppfmu::FMIBoolean* earlyReturn,
        cppfmu::FMIFloat64& endOfStep) override;

    void SetFloat64(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIFloat64* value, std::size_t nValues) override;
    void SetInt32(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIInt32* value, std::size_t nValues) override;
    void SetInt64(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIInt64* value, std::size_t nValues) override;
    void SetUInt64(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIUInt64* value, std::size_t nValues) override;
    void SetBoolean(const cppfmu::FMIValueReference* vr, std::size_t nvr, const cppfmu::FMIBoolean* value, std::size_t nValues) override;
    void SetString(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIString const* value, std::size_t nValues) override;

    void GetFloat64(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIFloat64* value, std::size_t nValues) const override;
    void GetInt32(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIInt32* value, std::size_t nValues) const override;
    void GetInt64(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIInt64* value, std::size_t nValues) const override;
    void GetUInt64(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIUInt64* value, std::size_t nValues) const override;
    void GetBoolean(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIBoolean* value, std::size_t nValues) const override;
    void GetString(const cppfmu::FMIValueReference* vr, std::size_t nvr, cppfmu::FMIString* value, std::size_t nValues) const override;

    void GetFMUstate(fmi3FMUState& State) override;
    void SetFMUstate(const fmi3FMUState& State) override;
    void FreeFMUstate(fmi3FMUState& State) override;
    
    // Model Exchange methods
    void GetContinuousStates(cppfmu::FMIFloat64* continuousStates, std::size_t nStates) const override;
    void GetNumberOfContinuousStates(std::size_t& nStates) const override;
    void GetNumberOfEventIndicators(std::size_t& nEventIndicators) const override;
    void GetContinuousStateDerivatives(cppfmu::FMIFloat64* derivatives, std::size_t nStates) const override;
    void GetNominalsOfContinuousStates(cppfmu::FMIFloat64* nominalContinuousStates, std::size_t nStates) const override;
    void GetEventIndicators(cppfmu::FMIFloat64* eventIndicators, std::size_t nEventIndicators) const override;
    void SetContinuousStates(const cppfmu::FMIFloat64* continuousStates, std::size_t nStates) override;
    void SetTime(cppfmu::FMIFloat64 time) override;
    void UpdateDiscreteStates(
        cppfmu::FMIBoolean* discreteStatesNeedUpdate,
        cppfmu::FMIBoolean* terminateSimulation,
        cppfmu::FMIBoolean* nominalContinuousStatesChanged,
        cppfmu::FMIBoolean* valuesOfContinuousStatesChanged,
        cppfmu::FMIBoolean* nextEventTimeDefined,
        cppfmu::FMIFloat64* nextEventTime) override;


    size_t SerializedFMUstateSize(const fmi3FMUState& State) override;
    void SerializeFMUstate(const fmi3FMUState& State, fmi3Byte bytes[], size_t size) override;
    void DeSerializeFMUstate(const fmi3Byte bytes[], size_t size, fmi3FMUState& State) override;

    void clearLogBuffer() const;

    ~PySlaveInstance() override;

private:
    std::shared_ptr<IPyState> pyState_;
    PyObject* pClass_{};
    PyObject* pInstance_{};
    PyObject* pMessages_{};

    const bool visible_;
    const std::string instanceName_;
    const std::string resources_;
    const cppfmu::Logger& logger_;

    mutable std::vector<PyObject*> strBuffer;
    mutable std::vector<PyObject*> logStrBuffer;

    // Formats the pending Python exception (with traceback) and throws cppfmu::FatalError.
    // Must be called with the GIL held; never returns.
    [[noreturn]] void handle_py_exception(const std::string& what) const;

    // Helpers shared by the getters/setters. All require the GIL.
    void callVoidMethod(const char* method) const;
    // Takes ownership of valuesList (may be nullptr if building it failed).
    void callSetter(const char* method, const cppfmu::FMIValueReference* vr, std::size_t nvr, PyObject* valuesList);
    // Return new references to lists holding at least the requested number of items.
    PyObject* callGetter(const char* method, const cppfmu::FMIValueReference* vr, std::size_t nvr, std::size_t nValues) const;
    PyObject* callListMethod(const char* method, std::size_t expected) const;
    void checkListSize(PyObject* list, std::size_t expected, const char* method) const;

    inline void clearStrBuffer() const
    {
        if (!strBuffer.empty()) {
            for (auto obj : strBuffer) {
                Py_DECREF(obj);
            }
            strBuffer.clear();
        }
    }

    inline void clearLogStrBuffer() const
    {
        if (!logStrBuffer.empty()) {
            for (auto obj : logStrBuffer) {
                Py_DECREF(obj);
            }
            logStrBuffer.clear();
        }
    }

    // Releases every Python reference held by this instance. Safe to call more than once.
    inline void cleanPyObject()
    {
        clearLogBuffer();
        clearLogStrBuffer();
        clearStrBuffer();
        Py_CLEAR(pClass_);
        Py_CLEAR(pInstance_);
        Py_CLEAR(pMessages_);
    }
};

} // namespace pythonfmu

#endif
