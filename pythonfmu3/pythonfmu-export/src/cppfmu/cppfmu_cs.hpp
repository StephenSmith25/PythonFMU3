/* Copyright 2016-2019, SINTEF Ocean.
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
#ifndef CPPFMU_CS_HPP
#define CPPFMU_CS_HPP

#include "cppfmu_common.hpp"

#include <vector>
#include <memory>

namespace cppfmu
{

/* ============================================================================
 * CO-SIMULATION INTERFACE
 * ============================================================================
 */

/* A base class for co-simulation slave instances.
 *
 * To implement a co-simulation slave, create a class which publicly derives
 * from this one and override its virtual methods as required.  DoStep() is
 * the only function which it is mandatory to override.
 *
 * The methods map directly to the C functions defined by FMI 2.0 (and, with
 * some adaptations, FMI 1.0), so the documentation here is intentionally
 * sparse.  We refer to the FMI specifications for detailed information.
 */
class SlaveInstance
{
public:
    /* Called from fmi3SetupExperiment() (FMI 2.0) or fmiInitializeSlave()
     * (FMI 1.0).
     * Does nothing by default.
     */
    virtual void SetupExperiment(
        FMIBoolean toleranceDefined,
        FMIFloat64 tolerance,
        FMIFloat64 tStart,
        FMIBoolean stopTimeDefined,
        FMIFloat64 tStop);

    /* Called from fmi3EnterInitializationMode() (FMI 2.0) or
     * fmiInitializeSlave() (FMI 1.0).
     * Does nothing by default.
     */
    virtual void EnterInitializationMode();

    /* Called from fmi3ExitInitializationMode() (FMI 2.0) or
     * fmiInitializeSlave() (FMI 1.0).
     * Does nothing by default.
     */
    virtual void ExitInitializationMode();

    /* Called from fmi3Terminate()/fmiTerminateSlave().
     * Does nothing by default.
     */
    virtual void Terminate();

    /* Called from fmi3Reset()/fmiResetSlave().
     * Does nothing by default.
     */
    virtual void Reset();

    /* Called from fmi3SetXxx()/fmiSetXxx().
     * Throws std::logic_error by default.
     */
    virtual void SetFloat64(
        const FMIValueReference vr[],
        std::size_t nvr,
        const FMIFloat64 value[],
        std::size_t nValues);
    virtual void SetInt32(
        const FMIValueReference vr[],
        std::size_t nvr,
        const FMIInt32 value[]);
    virtual void SetInt64(
        const FMIValueReference vr[],
        std::size_t nvr,
        const FMIInt64 value[]);
    virtual void SetUInt64(
        const FMIValueReference vr[],
        std::size_t nvr,
        const FMIUInt64 value[]);
    virtual void SetBoolean(
        const FMIValueReference vr[],
        std::size_t nvr,
        const FMIBoolean value[]);
    virtual void SetString(
        const FMIValueReference vr[],
        std::size_t nvr,
        const FMIString value[]);

    /* Called from fmi3GetXxx()/fmiGetXxx().
     * Throws std::logic_error by default.
     */
    virtual void GetFloat64(
        const FMIValueReference vr[],
        std::size_t nvr,
        FMIFloat64 value[],
        std::size_t nValues) const;
    virtual void GetInt32(
        const FMIValueReference vr[],
        std::size_t nvr,
        FMIInt32 value[]) const;
    virtual void GetInt64(
        const FMIValueReference vr[],
        std::size_t nvr,
        FMIInt64 value[]) const;
    virtual void GetUInt64(
        const FMIValueReference vr[],
        std::size_t nvr,
        FMIUInt64 value[]) const;
    virtual void GetBoolean(
        const FMIValueReference vr[],
        std::size_t nvr,
        FMIBoolean value[]) const;
    virtual void GetString(
        const FMIValueReference vr[],
        std::size_t nvr,
        FMIString value[]) const;

    // Called from fmi3DoStep()/fmiDoStep(). Must be implemented in model code.
    virtual FMIStatus DoStep(
        FMIFloat64 currentCommunicationPoint,
        FMIFloat64 communicationStepSize,
        FMIBoolean newStep,
        FMIBoolean* eventHandlingNeeded,
        FMIBoolean* terminateSimulation,
        FMIBoolean* earlyReturn,
        FMIFloat64& endOfStep) = 0;

    virtual void GetFMUstate(fmi3FMUState& state) = 0;
    virtual void SetFMUstate(const fmi3FMUState& state) = 0;
    virtual void FreeFMUstate(fmi3FMUState& state) = 0;

    virtual size_t SerializedFMUstateSize(const fmi3FMUState& state) = 0;
    virtual void SerializeFMUstate(const fmi3FMUState& state, fmi3Byte bytes[], size_t size) = 0;
    virtual void DeSerializeFMUstate(const fmi3Byte bytes[], size_t size, fmi3FMUState& state) = 0;

    // The instance is destroyed in fmi3FreeInstance()/fmiFreeSlaveInstance().
    virtual ~SlaveInstance() CPPFMU_NOEXCEPT;
};

} // namespace cppfmu


/* A function which must be defined by model code, and which should create
 * and return a new slave instance.
 *
 * The returned instance must be managed by a std::unique_ptr with a deleter
 * of type std::function<void(void*)> that takes care of freeing the memory.
 * The simplest way to set this up is to use cppfmu::AllocateUnique() to
 * create the slave instance.
 *
 * Most of its parameters correspond to those of fmi3Instantiate() and
 * fmiInstantiateSlave(), except that 'functions' and 'loggingOn' have been
 * replaced with more convenient types:
 *
 *     memory = An object which the model code can use for memory management,
 *              typically in conjunction with cppfmu::Allocator,
 *              cppfmu::AllocateUnique(), etc.  Allocation and deallocation
 *              requests get forwarded to the simulation environment.
 *
 *     logger = An object which the model code can use to log messages (e.g.
 *              warnings or debug info).  The messages are forwarded to the
 *              simulation environment's logging facilities.
 *
 * Note that this function is declared in the global namespace.
 */
std::unique_ptr<cppfmu::SlaveInstance> CppfmuInstantiateSlave(
    cppfmu::FMIString instanceName,
    cppfmu::FMIString fmuGUID,
    cppfmu::FMIString fmuResourceLocation,
    cppfmu::FMIString mimeType,
    cppfmu::FMIFloat64 timeout,
    cppfmu::FMIBoolean visible,
    cppfmu::FMIBoolean interactive,
    const cppfmu::Logger& logger);


#endif // header guard
