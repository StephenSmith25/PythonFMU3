cmake_minimum_required(VERSION 3.10)
project(pythonfmu-export VERSION 0.2.0)

# ==============================================================================
# Build settings
# ==============================================================================

set(BUILD_SHARED_LIBS ON)

# ==============================================================================
# Global internal configuration
# ==============================================================================

if (MSVC)
  # https://stackoverflow.com/questions/14172856/compile-with-mt-instead-of-md-using-cmake
  set(CompilerFlags
          CMAKE_CXX_FLAGS
          CMAKE_CXX_FLAGS_DEBUG
          CMAKE_CXX_FLAGS_RELEASE
          CMAKE_C_FLAGS
          CMAKE_C_FLAGS_DEBUG
          CMAKE_C_FLAGS_RELEASE
          )
  foreach (CompilerFlag ${CompilerFlags})
    string(REPLACE "/MD" "/MT" ${CompilerFlag} "${${CompilerFlag}}")
  endforeach ()
endif ()

# Automatically export all symbols in Windows DLLs.
set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)

# ==============================================================================
# Dependencies
# ==============================================================================

# Force to use stable Python ABI https://docs.python.org/3/c-api/stable.html
add_compile_definitions(Py_LIMITED_API)
find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)
if (WIN32)
  set(Python3_LIBRARIES ${Python3_LIBRARY_DIRS}/python3.lib)
endif ()

if (WIN32)
  set(TARGET_PLATFORM windows)
elseif (APPLE)
  set(TARGET_PLATFORM darwin)
else ()
  set(TARGET_PLATFORM linux)
endif ()

# FMI 3.0 platform tuple <arch>-<sys>; must match pythonfmu3/osutil.py:get_fmu_arch().
# The architecture is the one being *built for*: the Visual Studio -A option, or a single
# CMAKE_OSX_ARCHITECTURES entry on macOS, take precedence over the host processor.
if (CMAKE_GENERATOR_PLATFORM)
  set(_arch "${CMAKE_GENERATOR_PLATFORM}")
elseif (APPLE AND CMAKE_OSX_ARCHITECTURES)
  list(LENGTH CMAKE_OSX_ARCHITECTURES _n_arch)
  if (NOT _n_arch EQUAL 1)
    message(FATAL_ERROR "Universal builds are not supported: set CMAKE_OSX_ARCHITECTURES to a single architecture")
  endif ()
  set(_arch "${CMAKE_OSX_ARCHITECTURES}")
else ()
  set(_arch "${CMAKE_SYSTEM_PROCESSOR}")
endif ()
string(TOLOWER "${_arch}" _arch)

if (_arch MATCHES "^(aarch64|arm64|armv8)")
  set(_fmi_arch aarch64)
elseif (_arch MATCHES "^arm")
  set(_fmi_arch aarch32)
elseif (_arch MATCHES "^(x86_64|amd64|x64|i[3-6]86|x86|win32)$")
  set(_fmi_arch x86)
else ()
  set(_fmi_arch "${_arch}")
endif ()

if ("${CMAKE_SIZEOF_VOID_P}" STREQUAL "8")
  if (_fmi_arch STREQUAL "x86")
    set(_fmi_arch x86_64)
  elseif (_fmi_arch STREQUAL "aarch32")
    set(_fmi_arch aarch64)
  endif ()
elseif (_fmi_arch STREQUAL "aarch64")
  set(_fmi_arch aarch32)
endif ()

set(TARGET_PLATFORM ${_fmi_arch}-${TARGET_PLATFORM})

message("Building pythonfmu-export for platform ${TARGET_PLATFORM}")

add_subdirectory(src)
