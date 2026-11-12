// Linux/macOS loader shim.
//
// The importer loads this library (binaries/<platform>/<modelIdentifier>.so|.dylib). It
// deliberately has no link-time dependency on Python, so it can be loaded by any FMI
// importer (OMSimulator, fmusim, Simulink, ...), not just Python-based ones.
//
// On the first instantiation it:
//   1. makes the Python C API available process-wide: if the host process does not
//      already provide it (Python-based importers such as FMPy do), libpython is opened
//      with RTLD_GLOBAL, which also lets extension modules such as numpy resolve it;
//   2. loads the backend library (libpythonfmu-backend) from the same folder as this
//      library, and resolves the FMI functions it implements.
//
// libpython is searched for in this order:
//   - the PYTHONFMU_PYTHON_LIBRARY environment variable (a full path),
//   - resources/pythonfmu_libpython.txt (written by the builder: the library of the
//     Python that built the FMU, one candidate path per line),
//   - common library names for Python 3.8 - 3.14.

#include "shim/shim_loader.hpp"

#include <dlfcn.h>

#include <cstdlib>
#include <fstream>
#include <mutex>
#include <sstream>
#include <string>
#include <vector>

namespace pythonfmu_shim
{
namespace
{

#ifdef __APPLE__
const char* const kBackendFile = "libpythonfmu-backend.dylib";
#else
const char* const kBackendFile = "libpythonfmu-backend.so";
#endif

std::mutex g_mutex;
bool g_loaded = false;
std::vector<void*> g_functions;

bool pythonAlreadyAvailable()
{
    return dlsym(RTLD_DEFAULT, "Py_IsInitialized") != nullptr;
}

std::string directoryOfThisLibrary()
{
    Dl_info info{};
    if (dladdr(reinterpret_cast<void*>(&directoryOfThisLibrary), &info) == 0 || info.dli_fname == nullptr) {
        return ".";
    }
    std::string path = info.dli_fname;
    const auto slash = path.find_last_of('/');
    return slash == std::string::npos ? "." : path.substr(0, slash);
}

std::string resourceDirectory(const char* resourcePath)
{
    if (resourcePath == nullptr) return {};
    std::string path = resourcePath;
    const std::string scheme = "file://";
    if (path.compare(0, scheme.size(), scheme) == 0) path.erase(0, scheme.size());
    while (path.size() > 1 && path.back() == '/') path.pop_back();
    return path;
}

std::vector<std::string> libpythonCandidates(const std::string& resources)
{
    std::vector<std::string> candidates;
    if (const char* env = std::getenv("PYTHONFMU_PYTHON_LIBRARY")) {
        if (*env != '\0') candidates.emplace_back(env);
    }
    if (!resources.empty()) {
        std::ifstream hints(resources + "/pythonfmu_libpython.txt");
        std::string line;
        while (std::getline(hints, line)) {
            while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
            if (!line.empty()) candidates.push_back(line);
        }
    }
    for (int minor = 14; minor >= 8; --minor) {
        const std::string v = "3." + std::to_string(minor);
#ifdef __APPLE__
        candidates.push_back("libpython" + v + ".dylib");
        candidates.push_back("/opt/homebrew/opt/python@" + v + "/Frameworks/Python.framework/Versions/" + v + "/Python");
        candidates.push_back("/usr/local/opt/python@" + v + "/Frameworks/Python.framework/Versions/" + v + "/Python");
        candidates.push_back("/Library/Frameworks/Python.framework/Versions/" + v + "/Python");
#else
        candidates.push_back("libpython" + v + ".so.1.0");
        candidates.push_back("libpython" + v + ".so");
#endif
    }
    return candidates;
}

void report(fmi3InstanceEnvironment env, fmi3LogMessageCallback logMessage, const std::string& msg)
{
    if (logMessage != nullptr) logMessage(env, fmi3Fatal, "logStatusFatal", msg.c_str());
}

} // namespace

bool ensureBackendLoaded(fmi3String resourcePath, fmi3InstanceEnvironment env, fmi3LogMessageCallback logMessage)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_loaded) return true;

    if (!pythonAlreadyAvailable()) {
        std::ostringstream errors;
        bool found = false;
        for (const auto& candidate : libpythonCandidates(resourceDirectory(resourcePath))) {
            if (dlopen(candidate.c_str(), RTLD_NOW | RTLD_GLOBAL) != nullptr && pythonAlreadyAvailable()) {
                found = true;
                break;
            }
            const char* err = dlerror();
            errors << "\n  " << candidate << ": " << (err ? err : "loaded, but Py_IsInitialized not found");
        }
        if (!found) {
            report(env, logMessage,
                "PythonFMU3: unable to load the Python shared library (libpython). Set the "
                "PYTHONFMU_PYTHON_LIBRARY environment variable to its full path. Tried:" + errors.str());
            return false;
        }
    }

    const std::string backendPath = directoryOfThisLibrary() + "/" + kBackendFile;
    // Never closed: the backend keeps the Python interpreter (and a thread) alive.
    void* backend = dlopen(backendPath.c_str(), RTLD_NOW | RTLD_LOCAL);
    if (backend == nullptr) {
        const char* err = dlerror();
        report(env, logMessage, "PythonFMU3: unable to load " + backendPath + ": " + (err ? err : "unknown error"));
        return false;
    }

    std::vector<void*> functions(kFunctionCount, nullptr);
    for (std::size_t i = 0; i < kFunctionCount; i++) {
        functions[i] = dlsym(backend, (std::string(kBackendPrefix) + kFunctionNames[i]).c_str());
    }
    g_functions = std::move(functions);
    g_loaded = true;
    return true;
}

void* function(std::size_t index)
{
    // g_functions is written once, under the mutex, before any instance exists; every
    // later call is made on an instance and therefore happens after that write.
    return index < g_functions.size() ? g_functions[index] : nullptr;
}

} // namespace pythonfmu_shim
