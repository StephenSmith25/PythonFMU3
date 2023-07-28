/* Copyright 2016-2019, SINTEF Ocean.
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
#include "cppfmu/cppfmu_cs.hpp"

#include <exception>
#include <limits>


namespace
{
// A struct that holds all the data for one model instance.
struct Component
{
    Component(
        cppfmu::FMIString instanceName,
        cppfmu::FMICallbackLogger logCallback,
        cppfmu::FMIBoolean loggingOn)
        : loggerSettings{std::make_shared<cppfmu::Logger::Settings>()}
        , logger{this, instanceName, logCallback, loggerSettings}
        , lastSuccessfulTime{std::numeric_limits<cppfmu::FMIReal>::quiet_NaN()}
    {
        loggerSettings->debugLoggingEnabled = (loggingOn == cppfmu::FMITrue);
    }

    // General
    std::shared_ptr<cppfmu::Logger::Settings> loggerSettings;
    cppfmu::Logger logger;

    // Co-simulation
    std::unique_ptr<cppfmu::SlaveInstance> slave;
    cppfmu::FMIReal lastSuccessfulTime;
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


fmi3Instance fmi3InstantiateCoSimulationType(
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
        auto component = new Component(instanceName,
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


void fmi3FreeInstance(fmi3Instance c)
{
    const auto component = reinterpret_cast<Component*>(c);
    // The Component object was allocated using cppfmu::AllocateUnique(),
    // which uses cppfmu::New() internally, so we use cppfmu::Delete() to
    // release it again.
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
        component->slave->GetReal(vr, nvr, values);
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
        component->slave->GetInteger(vr, nvr, values);
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


fmi3Status fmi3SetReal(
    fmi3Instance c,
    const fmi3ValueReference vr[],
    size_t nvr,
    const fmi3Float64 value[],
    size_t nValues)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        component->slave->SetReal(vr, nvr, value);
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
        component->slave->SetInteger(vr, nvr, values);
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

fmi3Status fmi3DeSerializeFMUState(
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

fmi3Status fmi3OutputDerivatives(
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
    fmi3Boolean /*noSetFMUStatePriorToCurrentPoint*/,
    fmi3Boolean*,
    fmi3Boolean*,
    fmi3Boolean*,
    fmi3Float64*)
{
    const auto component = reinterpret_cast<Component*>(c);
    try {
        double endTime = currentCommunicationPoint;
        const auto ok = component->slave->DoStep(
            currentCommunicationPoint,
            communicationStepSize,
            fmi3True,
            endTime);
        if (ok) {
            component->lastSuccessfulTime =
                currentCommunicationPoint + communicationStepSize;
            return fmi3OK;
        } else {
            component->lastSuccessfulTime = endTime;
            return fmi3Discard;
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