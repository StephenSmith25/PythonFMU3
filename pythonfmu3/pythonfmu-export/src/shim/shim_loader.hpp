#ifndef PYTHONFMU_SHIM_LOADER_HPP
#define PYTHONFMU_SHIM_LOADER_HPP

// Linux/macOS only. See shim_loader.cpp.

#include "fmi/fmi3Functions.h"

#include <cstddef>

namespace pythonfmu_shim
{

// Symbol prefix the backend library is compiled with (FMI3_FUNCTION_PREFIX).
constexpr const char* kBackendPrefix = "pythonfmu_backend_";

// Generated (fmi3_forwarders.cpp): FMI functions forwarded to the backend, by index.
extern const char* const kFunctionNames[];
extern const std::size_t kFunctionCount;

// Makes libpython available (if needed) and loads the backend library. Thread-safe and
// idempotent. On failure, reports through logMessage (if non-null) and returns false.
bool ensureBackendLoaded(fmi3String resourcePath, fmi3InstanceEnvironment env, fmi3LogMessageCallback logMessage);

// Backend implementation of kFunctionNames[index], or nullptr if not loaded/available.
void* function(std::size_t index);

} // namespace pythonfmu_shim

#endif
