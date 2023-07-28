/* Copyright 2016-2019, SINTEF Ocean.
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
#ifndef CPPFMU_COMMON_HPP
#define CPPFMU_COMMON_HPP

#include <algorithm>    // std::find()
#include <cstddef>      // std::size_t
#include <functional>   // std::function
#include <memory>       // std::shared_ptr, std::unique_ptr
#include <new>          // std::bad_alloc
#include <stdexcept>    // std::runtime_error
#include <string>       // std::basic_string, std::char_traits
#include <utility>      // std::forward
#include <vector>

extern "C"
{
#ifdef CPPFMU_USE_FMI_1_0
#   include "fmiFunctions.h"
#elif CPPFMU_USE_FMI_2_0
#   include "fmi/fmi3Functions.h"
#else
#   include "fmi/fmi3Functions.h"
#endif
}


// CPPFMU_NOEXCEPT evaluates to 'noexcept' on compilers that support it.
#if (__cplusplus >= 201103L) || (defined(_MSC_VER) && _MSC_VER >= 1900)
#   define CPPFMU_NOEXCEPT noexcept
#else
#   define CPPFMU_NOEXCEPT
#endif


namespace cppfmu
{

// Aliases for FMI types and enums
#ifdef CPPFMU_USE_FMI_1_0
    typedef fmiReal FMIReal;
    typedef fmiInteger FMIInteger;
    typedef fmiBoolean FMIBoolean;
    typedef fmiString FMIString;
    typedef fmiCallbackFunctions FMICallbackFunctions;
    typedef fmiCallbackAllocateMemory FMICallbackAllocateMemory;
    typedef fmiCallbackFreeMemory FMICallbackFreeMemory;
    typedef fmiCallbackLogger FMICallbackLogger;
    typedef fmiComponent FMIComponent;
    typedef fmiComponent FMIComponentEnvironment;
    typedef fmiStatus FMIStatus;
    typedef fmiValueReference FMIValueReference;

    const FMIBoolean FMIFalse = fmiFalse;
    const FMIBoolean FMITrue = fmiTrue;

    const FMIStatus FMIOK = fmiOK;
    const FMIStatus FMIWarning = fmiWarning;
    const FMIStatus FMIDiscard = fmiDiscard;
    const FMIStatus FMIError = fmiError;
    const FMIStatus FMIFatal = fmiFatal;
    const FMIStatus FMIPending = fmiPending;
#elif CPP_FMU_USE_FMI_2_0
    typedef fmi3Real FMIReal;
    typedef fmi3Integer FMIInteger;
    typedef fmi3Boolean FMIBoolean;
    typedef fmi3String FMIString;
    typedef fmi3CallbackFunctions FMICallbackFunctions;
    typedef fmi3CallbackAllocateMemory FMICallbackAllocateMemory;
    typedef fmi3CallbackFreeMemory FMICallbackFreeMemory;
    typedef fmi3CallbackLogger FMICallbackLogger;
    typedef fmi3Component FMIComponent;
    typedef fmi3ComponentEnvironment FMIComponentEnvironment;
    typedef fmi3Status FMIStatus;
    typedef fmi3ValueReference FMIValueReference;

    const FMIBoolean FMIFalse = fmi3False;
    const FMIBoolean FMITrue = fmi3True;

    const FMIStatus FMIOK = fmi3OK;
    const FMIStatus FMIWarning = fmi3Warning;
    const FMIStatus FMIDiscard = fmi3Discard;
    const FMIStatus FMIError = fmi3Error;
    const FMIStatus FMIFatal = fmi3Fatal;
    const FMIStatus FMIPending = fmi3Pending;
#else
    typedef fmi3Float64 FMIReal;
    typedef fmi3Int32 FMIInteger;
    typedef fmi3Boolean FMIBoolean;
    typedef fmi3String FMIString;
    typedef fmi3LogMessageCallback FMICallbackLogger;
    typedef fmi3Instance FMIComponent;
    typedef fmi3InstanceEnvironment FMIComponentEnvironment;
    typedef fmi3Status FMIStatus;
    typedef fmi3ValueReference FMIValueReference;

    const FMIBoolean FMIFalse = fmi3False;
    const FMIBoolean FMITrue = fmi3True;

    const FMIStatus FMIOK = fmi3OK;
    const FMIStatus FMIWarning = fmi3Warning;
    const FMIStatus FMIDiscard = fmi3Discard;
    const FMIStatus FMIError = fmi3Error;
    const FMIStatus FMIFatal = fmi3Fatal;

#endif

using String = std::string;

// ============================================================================
// ERROR HANDLING
// ============================================================================


/* Exception class that signals "fatal error", i.e. an error which means that
 * not only is the current model instance invalid, but all other instances of
 * the same model too.
 */
class FatalError : public std::runtime_error
{
public:
    FatalError(const char* msg) CPPFMU_NOEXCEPT : std::runtime_error{msg} { }
};


// ============================================================================
// LOGGING
// ============================================================================

namespace detail
{
    template<typename Container, typename Item>
    bool CanFind(const Container& container, const Item& item)
    {
        return container.end() != std::find(
            container.begin(),
            container.end(),
            item);
    }
}


/* A class that can be used to log messages from model code.  All messages are
 * forwarded to the logging facilities provided by the simulation environment.
 */
class Logger
{
public:
    struct Settings
    {
        bool debugLoggingEnabled = false;
        std::vector<String> loggedCategories;
    };

    Logger(
        FMIComponentEnvironment component,
        String instanceName,
        fmi3LogMessageCallback logCallback,
        std::shared_ptr<Settings> settings)
        : m_component{component}
        , m_instanceName(std::move(instanceName))
        , m_fmiLogger{logCallback}
        , m_settings{settings}
    {
    }

    // Logs a message.
    template<typename... Args>
    void Log(
        FMIStatus status,
        FMIString category,
        FMIString message,
        Args&&... args) CPPFMU_NOEXCEPT
    {
        if (m_settings->loggedCategories.empty() ||
            detail::CanFind(m_settings->loggedCategories, category)) {
            m_fmiLogger(
                m_component,
                status,
                category,
                message);
        }
    }

    /* Logs a debug message (if debug logging is enabled by the simulation
     * environment).
     */
    template<typename... Args>
    void DebugLog(
        FMIStatus status,
        FMIString category,
        FMIString message,
        Args&&... args) CPPFMU_NOEXCEPT
    {
        if (m_settings->debugLoggingEnabled) {
            Log(
                status,
                category,
                message,
                std::forward<Args>(args)...);
        }
    }

private:
    const FMIComponentEnvironment m_component;
    const String m_instanceName;
    const FMICallbackLogger m_fmiLogger;
    std::shared_ptr<Settings> m_settings;
};


} // namespace cppfmu
#endif // header guard
