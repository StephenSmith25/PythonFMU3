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

if ("${CMAKE_SIZEOF_VOID_P}" STREQUAL "8")
  set(TARGET_PLATFORM x86_64-${TARGET_PLATFORM})
else ()
  set(TARGET_PLATFORM x86-${TARGET_PLATFORM})
endif ()

message("Building pythonfmu-export for platform ${TARGET_PLATFORM}")

add_subdirectory(src)
