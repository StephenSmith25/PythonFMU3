
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

    void initialize(PyGILState_STATE gilState);

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
    PyObject* pClass_;
    PyObject* pInstance_{};
    PyObject* pMessages_{};

    const bool visible_;
    const std::string instanceName_;
    const std::string resources_;
    const cppfmu::Logger& logger_;

    mutable std::vector<PyObject*> strBuffer;
    mutable std::vector<PyObject*> logStrBuffer;

    void handle_py_exception(const std::string& what, PyGILState_STATE gilState) const;

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

    inline void cleanPyObject() const
    {
        clearLogBuffer();
        clearLogStrBuffer();
        clearStrBuffer();
        Py_XDECREF(pClass_);
        Py_XDECREF(pInstance_);
        Py_XDECREF(pMessages_);
    }
};

} // namespace pythonfmu

#endif
