/* Copyright 2016-2019, SINTEF Ocean.
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
#include "cppfmu/cppfmu_cs.hpp"

#include <exception>
#include <limits>

#define NOT_IMPLEMENTED throw std::logic_error("function " + std::string(__func__) + " not implemented")


#define NOT_IMPLEMENTED_GETTER(suffix, var) fmi3Status fmi3Get##suffix( \
    fmi3Instance c, \
    const fmi3ValueReference vr[], \
    size_t nValueReferences, \
    var values[], \
    size_t nValues) { NOT_IMPLEMENTED;}  

#define NOT_IMPLEMENTED_SETTER(suffix, var) fmi3Status fmi3Set##suffix ( \
    fmi3Instance c, \
    const fmi3ValueReference vr[], \
    size_t nValueReferences, \
    const var values[], \
    size_t nValues) { NOT_IMPLEMENTED;}  

namespace
{
// A struct that holds all the data for one model instance.
struct Component
{
    enum class State
    {
        StartAndEnd = 1 << 0,
        ConfigurationMode = 1 << 1,
        Instantiated = 1 << 2,
        InitializationMode = 1 << 3,
        EventMode = 1 << 4,
        ContinuousTimeMode = 1 << 5,
        StepMode = 1 << 6,
        ClockActivationMode = 1 << 7,
        StepDiscarded = 1 << 8,
        ReconfigurationMode = 1 << 9,
        IntermediateUpdateMode = 1 << 10,
        Terminated = 1 << 11,
        modelError = 1 << 12,
        modelFatal = 1 << 13,
    };
    Component(cppfmu::FMIComponentEnvironment instanceEnvironment,
        cppfmu::FMICallbackLogger logCallback,
        cppfmu::FMIBoolean loggingOn) : loggerSettings{std::make_shared<cppfmu::Logger::Settings>()},
        logger{instanceEnvironment, logCallback, loggerSettings}
    {
        loggerSettings->debugLoggingEnabled = (loggingOn == cppfmu::FMITrue);
    }

    // General
    std::shared_ptr<cppfmu::Logger::Settings> loggerSettings;
    cppfmu::Logger logger;
    State state;

    // Co-simulation
    std::unique_ptr<cppfmu::SlaveInstance> slave;
};
} // namespace


// FMI functions
extern "C" {

// =============================================================================
// FMI 3.0 functions
// =============================================================================


const char* fmi3GetVersion()
{
    return "3.0";
}


fmi3Instance fmi3InstantiateCoSimulation(
    fmi3String instanceName,
    fmi3String instantiationToken,
    fmi3String fmuResourceLocation,
    fmi3Boolean visible,
    fmi3Boolean loggingOn,
    fmi3Boolean eventModeUsed,
    fmi3Boolean earlyReturnAllowed,
    fmi3ValueReference const[],
    size_t nRequiredIntermediateVariables,
    fmi3InstanceEnvironment environment,
    fmi3LogMessageCallback logMessage,
    fmi3IntermediateUpdateCallback intermediateUpdate )
{
    try {
        auto component = new Component(
            environment,
            logMessage,
            loggingOn);
        component->slave = CppfmuInstantiateSlave(
            instanceName,
            instantiationToken,
            fmuResourceLocation,
            "application/x-fmu-sharedlibrary",
            0.0,
            visible,
            cppfmu::FMIFalse,
            component->logger);
        return component;
    } catch (const cppfmu::FatalError& e) {
        // functions->logger(nullptr, instanceName, fmi3Fatal, "", e.what());
        return nullptr;
    } catch (const std::exception& e) {
        // functions->logger(nullptr, instanceName, fmi3Error, "", e.what());
        return nullptr;
    }
}

fmi3Instance fmi3InstantiateModelExchange(
    fmi3String                 instanceName,
    fmi3String                 instantiationToken,
    fmi3String                 resourcePath,
    fmi3Boolean                visible,
    fmi3Boolean                loggingOn,
    fmi3InstanceEnvironment    instanceEnvironment,
    fmi3LogMessageCallback     logMessage)
{
    throw std::logic_error("Unsupported FMU instance type requested (only co-simulation is supported)");
}

fmi3Instance fmi3InstantiateScheduledExecution(
    fmi3String                     instanceName,
    fmi3String                     instantiationToken,
    fmi3String                     resourcePath,
    fmi3Boolean                    visible,
    fmi3Boolean                    loggingOn,
    fmi3InstanceEnvironment        instanceEnvironment,
    fmi3LogMessageCallback         logMessage,
    fmi3ClockUpdateCallback        clockUpdate,
    fmi3LockPreemptionCallback     lockPreemption,
    fmi3UnlockPreemptionCallback   unlockPreemption)
{
    throw std::logic_error("Unsupported FMU instance type requested (only co-simulation is supported)");
}


void fmi3FreeInstance(fmi3Instance c)
{
    const auto component = reinterpret_cast<Component*>(c);
    delete component;
}


fmi3Status fmi3SetDebugLogging(
    fmi3Instance c,
    fmi3Boolean loggingOn,
    size_t nCategories,
    const fmi3String categories[])
{
    const auto component = reinterpret_cast<Component*>(c);

    std::vector<cppfmu::String> newCategories;
    for (size_t i = 0; i < nCategories; ++i) {
        newCategories.push_back(categories[i]);
    }

    component->loggerSettings->debugLoggingEnabled = (loggingOn == fmi3True);
    component->loggerSettings->loggedCategories.swap(newCategories);
    return fmi3OK;
}

fmi3Status fmi3EnterInitializationMode(fmi3Instance c, fmi3Boolean, fmi3Float64, fmi3Float64, fmi3Boolean, fmi3Float64)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->EnterInitializationMode();
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}


fmi3Status fmi3ExitInitializationMode(fmi3Instance c)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->ExitInitializationMode();
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3EnterConfigurationMode(fmi3Instance c)
{
    
    const auto component = reinterpret_cast<Component*>(c);
    component->state = Component::State::ConfigurationMode;
    return fmi3OK;

}

fmi3Status fmi3ExitConfigurationMode(fmi3Instance c)
{
    const auto component = reinterpret_cast<Component*>(c);
    if (component->state == Component::State::ConfigurationMode)
    {
        component->state = Component::State::Instantiated;

    } else{
        component->state = Component::State::StepMode;
    }
    return fmi3OK;
}

fmi3Status fmi3EnterEventMode(fmi3Instance c)
{
    const auto component = reinterpret_cast<Component*>(c);
    component->state = Component::State::EventMode;
    return fmi3OK;
}

fmi3Status fmi3EnterStepMode(fmi3Instance c)
{
    const auto component = reinterpret_cast<Component*>(c);
    component->state = Component::State::StepMode;
    return fmi3OK;
}


fmi3Status fmi3Terminate(fmi3Instance c)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->Terminate();
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}


fmi3Status fmi3Reset(fmi3Instance c)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->Reset();
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}


fmi3Status fmi3GetFloat64(
    fmi3Instance c,
    const fmi3ValueReference vr[],
    size_t nvr,
    fmi3Float64 values[],
    size_t nValues)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->GetFloat64(vr, nvr, values, nValues);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3GetInt32(
    fmi3Instance c,
    const fmi3ValueReference vr[],
    size_t nvr,
    fmi3Int32 values[],
    size_t nValues)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->GetInt32(vr, nvr, values);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3GetInt64(
    fmi3Instance c,
    const fmi3ValueReference vr[],
    size_t nvr,
    fmi3Int64 values[],
    size_t nValues)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->GetInt64(vr, nvr, values);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3GetUInt64(
    fmi3Instance c,
    const fmi3ValueReference vr[],
    size_t nvr,
    fmi3UInt64 values[],
    size_t nValues)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->GetUInt64(vr, nvr, values);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3GetBoolean(
    fmi3Instance c,
    const fmi3ValueReference vr[],
    size_t nvr,
    fmi3Boolean values[],
    size_t nValues)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->GetBoolean(vr, nvr, values);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3GetString(
    fmi3Instance c,
    const fmi3ValueReference vr[],
    size_t nvr,
    fmi3String values[],
    size_t nValues)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->GetString(vr, nvr, values);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}


fmi3Status fmi3SetFloat64(
    fmi3Instance c,
    const fmi3ValueReference vr[],
    size_t nvr,
    const fmi3Float64 value[],
    size_t nValues)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->SetFloat64(vr, nvr, value, nValues);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3SetInt32(
    fmi3Instance c,
    const fmi3ValueReference vr[],
    size_t nvr,
    const fmi3Int32 values[],
    size_t nValues)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->SetInt32(vr, nvr, values);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3SetInt64(
    fmi3Instance c,
    const fmi3ValueReference vr[],
    size_t nvr,
    const fmi3Int64 values[],
    size_t nValues)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->SetInt64(vr, nvr, values);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3SetUInt64(
    fmi3Instance c,
    const fmi3ValueReference vr[],
    size_t nvr,
    const fmi3UInt64 values[],
    size_t nValues)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->SetUInt64(vr, nvr, values);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3SetBoolean(
    fmi3Instance c,
    const fmi3ValueReference vr[],
    size_t nvr,
    const fmi3Boolean values[],
    size_t nValues)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->SetBoolean(vr, nvr, values);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3SetString(
    fmi3Instance c,
    const fmi3ValueReference vr[],
    size_t nvr,
    const fmi3String values[],
    size_t nValues)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->SetString(vr, nvr, values);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}


fmi3Status fmi3GetFMUState(
    fmi3Instance c,
    fmi3FMUState* state)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->GetFMUstate(*state);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3SetFMUState(
    fmi3Instance c,
    fmi3FMUState state)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->SetFMUstate(state);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3FreeFMUState(
    fmi3Instance c,
    fmi3FMUState* state)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->FreeFMUstate(*state);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3SerializedFMUStateSize(
    fmi3Instance c,
    fmi3FMUState state,
    size_t* size)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        *size = component->slave->SerializedFMUstateSize(state);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3SerializeFMUState(
    fmi3Instance c,
    fmi3FMUState state,
    fmi3Byte bytes[],
    size_t size)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->SerializeFMUstate(state, bytes, size);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}

fmi3Status fmi3DeserializeFMUState(
    fmi3Instance c,
    const fmi3Byte bytes[],
    size_t size,
    fmi3FMUState* state)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->DeSerializeFMUstate(bytes, size, *state);
        return fmi3OK;
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}


fmi3Status fmi3GetDirectionalDerivative(
    fmi3Instance c,
    const fmi3ValueReference[],
    size_t,
    const fmi3ValueReference[],
    size_t,
    const fmi3Float64[],
    size_t,
    fmi3Float64[],
    size_t)
{
    reinterpret_cast<Component*>(c)->logger.Log(
        fmi3Error,
        "cppfmu",
        "FMI function not supported: fmi3GetDirectionalDerivative");
    return fmi3Error;
}

fmi3Status fmi3GetOutputDerivatives(
    fmi3Instance c,
    const fmi3ValueReference[],
    size_t,
    const fmi3Int32[],
    fmi3Float64[],
    size_t)
{
    reinterpret_cast<Component*>(c)->logger.Log(
        fmi3Error,
        "cppfmu",
        "FMI function not supported: fmiGetOutputDerivatives");
    return fmi3Error;
}

fmi3Status fmi3DoStep(
    fmi3Instance c,
    fmi3Float64 currentCommunicationPoint,
    fmi3Float64 communicationStepSize,
    fmi3Boolean noSetFmuStatePriorToCurrentPoint,
    fmi3Boolean* eventHandlingNeeded ,
    fmi3Boolean* terminateSimulation,
    fmi3Boolean* earlyReturn,
    fmi3Float64* lastSuccessfulTime)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        double endTime = currentCommunicationPoint;
        const auto status = component->slave->DoStep(
            currentCommunicationPoint,
            communicationStepSize,
            noSetFmuStatePriorToCurrentPoint,
            eventHandlingNeeded,
            terminateSimulation,
            earlyReturn,
            endTime);
        if (status == fmi3Status::fmi3OK) {
            *lastSuccessfulTime =
                currentCommunicationPoint + communicationStepSize;
            return fmi3OK;
        } else {
            *lastSuccessfulTime = endTime;
            return status;
        }
    } catch (const cppfmu::FatalError& e) {
        component->logger.Log(fmi3Fatal, "", e.what());
        return fmi3Fatal;
    } catch (const std::exception& e) {
        component->logger.Log(fmi3Error, "", e.what());
        return fmi3Error;
    }
}
}

// NOT IMPLEMENTED

NOT_IMPLEMENTED_GETTER(Float32, fmi3Float32);
NOT_IMPLEMENTED_SETTER(Float32, fmi3Float32);

NOT_IMPLEMENTED_GETTER(Int8, fmi3Int8);
NOT_IMPLEMENTED_SETTER(Int8, fmi3Int8);
NOT_IMPLEMENTED_GETTER(Int16, fmi3Int16);
NOT_IMPLEMENTED_SETTER(Int16, fmi3Int16);

NOT_IMPLEMENTED_GETTER(UInt8, fmi3UInt8);
NOT_IMPLEMENTED_SETTER(UInt8, fmi3UInt8);
NOT_IMPLEMENTED_GETTER(UInt16, fmi3UInt16);
NOT_IMPLEMENTED_SETTER(UInt16, fmi3UInt16);
NOT_IMPLEMENTED_GETTER(UInt32, fmi3UInt32);
NOT_IMPLEMENTED_SETTER(UInt32, fmi3UInt32);


fmi3Status fmi3GetClock(fmi3Instance instance,
    const fmi3ValueReference valueReferences[],
    size_t nValueReferences,
    fmi3Clock values[])
{
    NOT_IMPLEMENTED;
}

fmi3Status fmi3SetClock(fmi3Instance instance,
    const fmi3ValueReference valueReferences[],
    size_t nValueReferences,
    const fmi3Clock values[])
{
    NOT_IMPLEMENTED;
}

fmi3Status fmi3GetBinary(fmi3Instance instance,
    const fmi3ValueReference valueReferences[],
    size_t nValueReferences,
    size_t valueSizes[],
    fmi3Binary values[],
    size_t nValues)
{

    NOT_IMPLEMENTED;
}

fmi3Status fmi3SetBinary(fmi3Instance instance,
    const fmi3ValueReference valueReferences[],
    size_t nValueReferences,
    const size_t valueSizes[],
    const fmi3Binary values[],
    size_t nValues)
{
    NOT_IMPLEMENTED;
}

fmi3Status fmi3GetNumberOfVariableDependencies(fmi3Instance instance,
    fmi3ValueReference valueReference,
    size_t* nDependencies)
{
    NOT_IMPLEMENTED;
}

fmi3Status fmi3GetVariableDependencies(fmi3Instance instance,
    fmi3ValueReference dependent,
    size_t elementIndicesOfDependent[],
    fmi3ValueReference independents[],
    size_t elementIndicesOfIndependents[],
    fmi3DependencyKind dependencyKinds[],
    size_t nDependencies)
{
    NOT_IMPLEMENTED;
}

fmi3Status fmi3GetAdjointDerivative(fmi3Instance instance,
    const fmi3ValueReference unknowns[],
    size_t nUnknowns,
    const fmi3ValueReference knowns[],
    size_t nKnowns,
    const fmi3Float64 seed[],
    size_t nSeed,
    fmi3Float64 sensitivity[],
    size_t nSensitivity)
{
    NOT_IMPLEMENTED;
}

fmi3Status fmi3GetIntervalDecimal(
    fmi3Instance instance, 
    const fmi3ValueReference valueReferences[],
    size_t nValueReferences, 
    fmi3Float64 intervals[],
    fmi3IntervalQualifier qualifiers[])
{
  NOT_IMPLEMENTED;
}

fmi3Status fmi3GetIntervalFraction(
    fmi3Instance instance,
    const fmi3ValueReference valueReferences[],
    size_t nValueReferences,
    fmi3UInt64 intervalCounters[],
    fmi3UInt64 resolutions[],
    fmi3IntervalQualifier qualifiers[])
{
  NOT_IMPLEMENTED;
}

fmi3Status
fmi3GetShiftDecimal(fmi3Instance instance, const fmi3ValueReference valueReferences[],
    size_t nValueReferences, fmi3Float64 shifts[])
{
  NOT_IMPLEMENTED;
}

fmi3Status
fmi3GetShiftFraction(fmi3Instance instance, const fmi3ValueReference valueReferences[],
    size_t nValueReferences, fmi3UInt64 shiftCounters[], fmi3UInt64 resolutions[])
{
  NOT_IMPLEMENTED;
}

fmi3Status
fmi3SetIntervalDecimal(fmi3Instance instance, const fmi3ValueReference valueReferences[],
    size_t nValueReferences, const fmi3Float64 intervals[])
{
  NOT_IMPLEMENTED;
}

fmi3Status
fmi3SetIntervalFraction(fmi3Instance instance, const fmi3ValueReference valueReferences[],
    size_t nValueReferences, const fmi3UInt64 intervalCounters[],
    const fmi3UInt64 resolutions[])
{
  NOT_IMPLEMENTED;
}

fmi3Status
fmi3SetShiftDecimal(fmi3Instance instance, const fmi3ValueReference valueReferences[],
    size_t nValueReferences, const fmi3Float64 shifts[])
{
  NOT_IMPLEMENTED;
}

fmi3Status
fmi3SetShiftFraction(fmi3Instance instance, const fmi3ValueReference valueReferences[],
    size_t nValueReferences, const fmi3UInt64 shiftCounters[],
    const fmi3UInt64 resolutions[])
{
  NOT_IMPLEMENTED;
}

fmi3Status
fmi3EvaluateDiscreteStates(fmi3Instance instance)
{
  NOT_IMPLEMENTED;
}

fmi3Status
fmi3UpdateDiscreteStates(fmi3Instance instance, fmi3Boolean* discreteStatesNeedUpdate,
    fmi3Boolean* terminateSimulation,
    fmi3Boolean* nominalsOfContinuousStatesChanged,
    fmi3Boolean* valuesOfContinuousStatesChanged,
    fmi3Boolean* nextEventTimeDefined, fmi3Float64* nextEventTime)
{
  NOT_IMPLEMENTED;
}

fmi3Status fmi3ActivateModelPartition(fmi3Instance instance, fmi3ValueReference clockReference,
    fmi3Float64 activationTime)
{
  NOT_IMPLEMENTED;
}


// model exchange functions
fmi3Status
fmi3EnterContinuousTimeMode(fmi3Instance instance)
{
    NOT_IMPLEMENTED;
}

fmi3Status
fmi3CompletedIntegratorStep(fmi3Instance instance, fmi3Boolean noSetFMUStatePriorToCurrentPoint,
                            fmi3Boolean* enterEventMode, fmi3Boolean* terminateSimulation)
{
    NOT_IMPLEMENTED;
}

/* Providing independent variables and re-initialization of caching */
fmi3Status
fmi3SetTime(fmi3Instance instance, fmi3Float64 time)
{
    NOT_IMPLEMENTED;
}

fmi3Status
fmi3SetContinuousStates(fmi3Instance instance, const fmi3Float64 continuousStates[],
    size_t nContinuousStates)
{
    NOT_IMPLEMENTED;
}

/* Evaluation of the model equations */
fmi3Status
fmi3GetContinuousStateDerivatives(fmi3Instance instance, fmi3Float64 derivatives[],
    size_t nContinuousStates)
{
    NOT_IMPLEMENTED;
}

fmi3Status
fmi3GetEventIndicators(fmi3Instance instance, fmi3Float64 eventIndicators[],
    size_t nEventIndicators)
{
    NOT_IMPLEMENTED;
}

fmi3Status
fmi3GetContinuousStates(fmi3Instance instance, fmi3Float64 continuousStates[],
    size_t nContinuousStates)
{
    NOT_IMPLEMENTED;
}

fmi3Status
fmi3GetNominalsOfContinuousStates(fmi3Instance instance, fmi3Float64 nominals[],
    size_t nContinuousStates)
{
    NOT_IMPLEMENTED;
}

fmi3Status
fmi3GetNumberOfEventIndicators(fmi3Instance instance, size_t* nEventIndicators)
{
    NOT_IMPLEMENTED;
}

fmi3Status
fmi3GetNumberOfContinuousStates(fmi3Instance instance, size_t* nContinuousStates)
{
    NOT_IMPLEMENTED;
}
